import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@app.route('/')
def home():
    return "API Online! Use /api/torneio/val para testar."

# --- AUXILIAR: Achar ID do Torneio pelo Jogo ---
def get_tournament_id(game_tag):
    # Procura na tabela tournaments onde game = 'val', 'cs' ou 'fifa'
    res = supabase.table('tournaments').select('id').eq('game', game_tag).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]['id']
    return None

# --- AUXILIAR: Criar ou Achar Time ---
def get_or_create_team(name):
    if not name or name.strip() == "": return None
    res = supabase.table('teams').select('id').eq('name', name).execute()
    if res.data: return res.data[0]['id']
    new_team = supabase.table('teams').insert({'name': name}).execute()
    return new_team.data[0]['id']

# --- ROTA GET INTELIGENTE (Resolve o erro 404) ---
@app.route('/api/torneio/<game_tag>', methods=['GET'])
def get_torneio(game_tag):
    tournament_id = get_tournament_id(game_tag)
    
    # Se o torneio ainda não existe no banco, retorna vazio (não erro 404)
    if not tournament_id:
        return jsonify({}) 

    # Busca partidas
    response = supabase.table('matches')\
        .select('position_code, score1, score2, team1:team1_id(name), team2:team2_id(name)')\
        .eq('tournament_id', tournament_id)\
        .execute()
    
    frontend_data = {"formato": "16"} # Padrão
    
    for match in response.data:
        code = match['position_code']
        t1_name = match['team1']['name'] if match['team1'] else ""
        t2_name = match['team2']['name'] if match['team2'] else ""
        
        if code == 'final':
            frontend_data['ft1n'] = t1_name; frontend_data['ft2n'] = t2_name
            frontend_data['ft1s'] = match['score1']; frontend_data['ft2s'] = match['score2']
        else:
            frontend_data[f"{code}t1n"] = t1_name; frontend_data[f"{code}t2n"] = t2_name
            frontend_data[f"{code}t1s"] = match['score1']; frontend_data[f"{code}t2s"] = match['score2']

    return jsonify(frontend_data)

# --- ROTA POST (Salvar) ---
@app.route('/api/torneio', methods=['POST'])
def save_torneio():
    try:
        content = request.json
        game_tag = content.get('jogo_id') # ex: 'val'
        dados = content.get('dados')

        # 1. Garante que o Torneio Existe
        tour_id = get_tournament_id(game_tag)
        if not tour_id:
            # Se não existe, cria agora
            new_tour = supabase.table('tournaments').insert({'name': f'Copa {game_tag.upper()}', 'game': game_tag}).execute()
            tour_id = new_tour.data[0]['id']
            # Cria os slots vazios (esqueleto) para esse novo torneio
            # (Simplificado: assume que o admin vai salvar de novo se falhar)

        # 2. Salva os dados
        codes = [f'o{i}' for i in range(1,9)] + [f'q{i}' for i in range(1,5)] + ['s1','s2','final']

        for code in codes:
            if code == 'final':
                n1, s1 = dados.get('f-t1-n'), dados.get('f-t1-s')
                n2, s2 = dados.get('f-t2-n'), dados.get('f-t2-s')
            else:
                n1, s1 = dados.get(f'{code}-t1-n'), dados.get(f'{code}-t1-s')
                n2, s2 = dados.get(f'{code}-t2-n'), dados.get(f'{code}-t2-s')

            t1_id = get_or_create_team(n1)
            t2_id = get_or_create_team(n2)

            # Upsert na partida
            match_data = {
                'tournament_id': tour_id, 'position_code': code,
                'team1_id': t1_id, 'team2_id': t2_id,
                'score1': int(s1) if s1 else 0, 'score2': int(s2) if s2 else 0
            }
            
            # Tenta atualizar, se não der insert (lógica simplificada via upsert do supabase exige unique constraint)
            # Vamos usar delete+insert ou check de existência. 
            # Para facilitar, vamos tentar UPDATE, se não afetar linhas, faz INSERT.
            
            upd = supabase.table('matches').update(match_data).eq('tournament_id', tour_id).eq('position_code', code).execute()
            if len(upd.data) == 0:
                 supabase.table('matches').insert(match_data).execute()

        return jsonify({"msg": "Salvo!"})
    except Exception as e:
        print(e)
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
