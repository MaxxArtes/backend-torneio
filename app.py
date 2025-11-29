import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
# Permite que qualquer origem (seu site local ou na nuvem) acesse a API
CORS(app, resources={r"/*": {"origins": "*"}})

# --- CONFIGURAÇÃO DO SUPABASE ---
# Certifique-se de definir essas variáveis de ambiente no Render ou no seu .env local
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Faltam as variáveis SUPABASE_URL e SUPABASE_KEY")

supabase: Client = create_client(url, key)

@app.route('/')
def home():
    return "API Backend E-Sports (Schema UUID) Online! 🚀"

# ==============================================================================
# FUNÇÕES AUXILIARES (Lógica de Banco de Dados)
# ==============================================================================

def get_tournament_id(game_tag):
    """Busca o ID (UUID) do torneio baseado na tag do jogo (val, cs, fifa)."""
    try:
        res = supabase.table('tournaments').select('id').eq('game', game_tag).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['id']
        return None
    except Exception as e:
        print(f"Erro ao buscar torneio: {e}")
        return None

def get_or_create_team(name):
    """Busca o ID (UUID) de um time pelo nome. Se não existir, cria um novo."""
    if not name or name.strip() == "": 
        return None
    
    try:
        # 1. Tenta achar o time
        res = supabase.table('teams').select('id').eq('name', name).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['id']
        
        # 2. Se não achou, cria
        new_team = supabase.table('teams').insert({'name': name}).execute()
        if new_team.data and len(new_team.data) > 0:
            return new_team.data[0]['id']
            
    except Exception as e:
        print(f"Erro ao gerenciar time '{name}': {e}")
    
    return None

def determine_round(code):
    """Define o nome da rodada baseado no código da posição para salvar no banco."""
    if code.startswith('p'): return 'Preliminar'
    if code.startswith('o'): return 'Oitavas'
    if code.startswith('q'): return 'Quartas'
    if code.startswith('s'): return 'Semifinal'
    if code == 'final': return 'Final'
    return 'Desconhecido'

# ==============================================================================
# ROTA 1: GET - Buscar dados para o Site e Admin
# ==============================================================================
@app.route('/api/torneio/<game_tag>', methods=['GET'])
def get_torneio(game_tag):
    try:
        tournament_id = get_tournament_id(game_tag)
        
        # Se o torneio não existe, retorna vazio (mas 200 OK)
        if not tournament_id:
            return jsonify({}) 

        # Busca partidas fazendo JOIN com a tabela teams para pegar os nomes
        # Sintaxe Supabase para JOIN: team1:team1_id(name) -> Traz o objeto team1 com o campo name
        response = supabase.table('matches')\
            .select('position_code, score1, score2, team1:team1_id(name), team2:team2_id(name)')\
            .eq('tournament_id', tournament_id)\
            .execute()
        
        # Objeto que será devolvido para o Frontend
        frontend_data = {"formato": "16"} # Padrão
        
        for match in response.data:
            code = match['position_code']
            
            # Extrai os nomes (trata caso seja None/Null no banco)
            t1_name = match['team1']['name'] if match.get('team1') else ""
            t2_name = match['team2']['name'] if match.get('team2') else ""
            s1 = match['score1']
            s2 = match['score2']
            
            # Ajuste de prefixo para a Final (para bater com o ID do HTML)
            prefix = "f" if code == 'final' else code

            # --- PREENCHE OS DADOS ---
            
            # 1. Formato compactado (para o Site Público gerar o Bracket)
            # Ex: o1t1n (Oitavas 1, Time 1, Nome)
            frontend_data[f"{prefix}t1n"] = t1_name
            frontend_data[f"{prefix}t2n"] = t2_name
            frontend_data[f"{prefix}t1s"] = s1
            frontend_data[f"{prefix}t2s"] = s2

            # 2. Formato com traços (para o Painel Admin preencher os inputs)
            # Ex: o1-t1-n
            frontend_data[f"{prefix}-t1-n"] = t1_name
            frontend_data[f"{prefix}-t2-n"] = t2_name
            frontend_data[f"{prefix}-t1-s"] = s1
            frontend_data[f"{prefix}-t2-s"] = s2

        return jsonify(frontend_data)

    except Exception as e:
        print(f"Erro no GET: {e}")
        return jsonify({"erro": str(e)}), 500


# ==============================================================================
# ROTA 2: POST - Salvar dados do Admin
# ==============================================================================
@app.route('/api/torneio', methods=['POST'])
def save_torneio():
    try:
        content = request.json
        game_tag = content.get('jogo_id') # 'val', 'cs', 'fifa'
        dados = content.get('dados')

        if not game_tag or not dados:
            return jsonify({"erro": "Dados inválidos"}), 400

        # 1. Garante que o Torneio Existe
        tour_id = get_tournament_id(game_tag)
        if not tour_id:
            # Cria novo torneio se não existir
            new_tour = supabase.table('tournaments').insert({
                'name': f'Copa {game_tag.upper()}', 
                'game': game_tag
            }).execute()
            tour_id = new_tour.data[0]['id']

        # 2. Lista de códigos de partida possíveis
        codes = [f'p{i}' for i in range(1,7)] + \
                [f'o{i}' for i in range(1,9)] + \
                [f'q{i}' for i in range(1,5)] + \
                ['s1','s2','final']

        # 3. Itera sobre cada partida e salva/atualiza
        for code in codes:
            # Define o prefixo usado no JSON do frontend ('f' para final, ou o próprio código)
            prefix = 'f' if code == 'final' else code

            # Pega os valores dos inputs
            n1 = dados.get(f'{prefix}-t1-n')
            s1 = dados.get(f'{prefix}-t1-s')
            n2 = dados.get(f'{prefix}-t2-n')
            s2 = dados.get(f'{prefix}-t2-s')

            # Converte placar para Inteiro (ou 0 se vazio)
            score1 = int(s1) if s1 and s1 != "" else 0
            score2 = int(s2) if s2 and s2 != "" else 0

            # Busca ou Cria os Times (retorna UUIDs)
            t1_id = get_or_create_team(n1)
            t2_id = get_or_create_team(n2)

            # Calcula quem é o vencedor (opcional, para preencher seu campo winner_id)
            winner_id = None
            if t1_id and t2_id: # Só calcula se tiver dois times
                if score1 > score2: winner_id = t1_id
                elif score2 > score1: winner_id = t2_id

            # Monta o objeto para salvar no banco
            match_data = {
                'tournament_id': tour_id,
                'position_code': code,
                'round': determine_round(code), # Preenche seu campo 'round'
                'team1_id': t1_id,
                'team2_id': t2_id,
                'score1': score1,
                'score2': score2,
                'winner_id': winner_id
            }
            
            # --- LÓGICA DE UPSERT (ATUALIZAR OU INSERIR) ---
            # Verifica se essa partida (torneio + posição) já existe
            existing = supabase.table('matches')\
                .select('id')\
                .eq('tournament_id', tour_id)\
                .eq('position_code', code)\
                .execute()
            
            if existing.data and len(existing.data) > 0:
                # Atualiza (UPDATE)
                match_db_id = existing.data[0]['id']
                supabase.table('matches').update(match_data).eq('id', match_db_id).execute()
            else:
                # Insere (INSERT) apenas se houver pelo menos um time ou placar definido
                # (Isso evita criar linhas vazias no banco para jogos não usados)
                if t1_id or t2_id or score1 > 0 or score2 > 0:
                    supabase.table('matches').insert(match_data).execute()

        return jsonify({"msg": "Salvo com sucesso!"})

    except Exception as e:
        print(f"ERRO CRÍTICO NO BACKEND: {e}")
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    # Roda na porta 10000 (padrão do Render para Flask muitas vezes) ou 5000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
