import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# ID do Torneio Padrão (Criado no SQL acima)
TOURNAMENT_ID = '00000000-0000-0000-0000-000000000001'

@app.route('/')
def home():
    return "API Relacional Online 🚀"

# --- FUNÇÃO AUXILIAR: Achar ou Criar Time ---
def get_or_create_team(name):
    if not name or name.strip() == "": return None
    
    # 1. Tenta achar
    res = supabase.table('teams').select('id').eq('name', name).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]['id']
    
    # 2. Se não achar, cria
    new_team = supabase.table('teams').insert({'name': name}).execute()
    return new_team.data[0]['id']

# --- ROTA GET: Busca dados formatados para o HTML ---
@app.route('/api/torneio', methods=['GET'])
def get_torneio():
    # Busca todas as partidas do torneio e JOINS com times
    # A sintaxe team1:team1_id(name) pega o NOME do time através do ID
    response = supabase.table('matches')\
        .select('position_code, score1, score2, team1:team1_id(name), team2:team2_id(name)')\
        .eq('tournament_id', TOURNAMENT_ID)\
        .execute()
    
    # Transforma o formato Banco de Dados -> Formato HTML (JSON Simples)
    frontend_data = {}
    for match in response.data:
        code = match['position_code'] # ex: 'o1'
        
        # Garante que não quebre se o time for nulo
        t1_name = match['team1']['name'] if match['team1'] else ""
        t2_name = match['team2']['name'] if match['team2'] else ""
        
        if code == 'final':
            frontend_data['ft1n'] = t1_name
            frontend_data['ft2n'] = t2_name
            frontend_data['ft1s'] = match['score1']
            frontend_data['ft2s'] = match['score2']
        else:
            frontend_data[f"{code}t1n"] = t1_name
            frontend_data[f"{code}t2n"] = t2_name
            frontend_data[f"{code}t1s"] = match['score1']
            frontend_data[f"{code}t2s"] = match['score2']

    return jsonify(frontend_data)

# --- ROTA POST: Salva e organiza os IDs ---
@app.route('/api/torneio', methods=['POST'])
def save_torneio():
    data = request.json.get('dados', {})
    
    # Lista de códigos de partidas que seu HTML usa
    codes = []
    for i in range(1, 9): codes.append(f'o{i}')
    for i in range(1, 5): codes.append(f'q{i}')
    for i in range(1, 3): codes.append(f's{i}')
    codes.append('final')

    for code in codes:
        # Descobre os nomes digitados no HTML
        if code == 'final':
            name1 = data.get('f-t1-n')
            score1 = data.get('f-t1-s')
            name2 = data.get('f-t2-n')
            score2 = data.get('f-t2-s')
        else:
            name1 = data.get(f'{code}-t1-n')
            score1 = data.get(f'{code}-t1-s')
            name2 = data.get(f'{code}-t2-n')
            score2 = data.get(f'{code}-t2-s')

        # Converte Nomes -> UUIDs (Salva na tabela teams se precisar)
        team1_id = get_or_create_team(name1)
        team2_id = get_or_create_team(name2)

        # Atualiza a partida na tabela matches
        update_data = {
            'team1_id': team1_id,
            'team2_id': team2_id,
            'score1': int(score1) if score1 else 0,
            'score2': int(score2) if score2 else 0
        }

        supabase.table('matches')\
            .update(update_data)\
            .eq('tournament_id', TOURNAMENT_ID)\
            .eq('position_code', code)\
            .execute()

    return jsonify({"msg": "Sucesso! Dados Relacionais Salvos."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
