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
    return "API E-Sports com Stream Control Online! 🚀"

def get_tournament_data(game_tag):
    # Busca ID e Link da Stream
    res = supabase.table('tournaments').select('id, stream_url').eq('game', game_tag).execute()
    if res.data and len(res.data) > 0:
        return res.data[0]
    return None

def get_or_create_team(name):
    if not name or name.strip() == "": return None
    res = supabase.table('teams').select('id').eq('name', name).execute()
    if res.data: return res.data[0]['id']
    new_team = supabase.table('teams').insert({'name': name}).execute()
    return new_team.data[0]['id']

@app.route('/api/torneio/<game_tag>', methods=['GET'])
def get_torneio(game_tag):
    tour_data = get_tournament_data(game_tag)
    if not tour_data: return jsonify({}) 

    tournament_id = tour_data['id']
    stream_url = tour_data.get('stream_url', '')

    response = supabase.table('matches')\
        .select('position_code, score1, score2, team1:team1_id(name), team2:team2_id(name)')\
        .eq('tournament_id', tournament_id)\
        .execute()
    
    # Adiciona a URL da stream na resposta
    frontend_data = {"formato": "16", "stream_url": stream_url}
    
    for match in response.data:
        code = match['position_code']
        t1_name = match['team1']['name'] if match.get('team1') else ""
        t2_name = match['team2']['name'] if match.get('team2') else ""
        prefix = "f" if code == 'final' else code

        frontend_data[f"{prefix}t1n"] = t1_name
        frontend_data[f"{prefix}t2n"] = t2_name
        frontend_data[f"{prefix}t1s"] = match['score1']
        frontend_data[f"{prefix}t2s"] = match['score2']
        frontend_data[f"{prefix}-t1-n"] = t1_name
        frontend_data[f"{prefix}-t2-n"] = t2_name
        frontend_data[f"{prefix}-t1-s"] = match['score1']
        frontend_data[f"{prefix}-t2-s"] = match['score2']

    return jsonify(frontend_data)

@app.route('/api/torneio', methods=['POST'])
def save_torneio():
    try:
        content = request.json
        game_tag = content.get('jogo_id')
        dados = content.get('dados')
        stream_url = content.get('stream_url') # Pega o link enviado pelo Admin

        tour_data = get_tournament_data(game_tag)
        if not tour_data:
            new_tour = supabase.table('tournaments').insert({'name': f'Copa {game_tag}', 'game': game_tag}).execute()
            tour_id = new_tour.data[0]['id']
        else:
            tour_id = tour_data['id']

        # 1. ATUALIZA O LINK DA STREAM NO BANCO
        supabase.table('tournaments').update({'stream_url': stream_url}).eq('id', tour_id).execute()

        # 2. SALVA OS JOGOS
        codes = [f'p{i}' for i in range(1,7)] + [f'o{i}' for i in range(1,9)] + \
                [f'q{i}' for i in range(1,5)] + ['s1','s2','final']

        for code in codes:
            prefix = 'f' if code == 'final' else code
            n1, s1 = dados.get(f'{prefix}-t1-n'), dados.get(f'{prefix}-t1-s')
            n2, s2 = dados.get(f'{prefix}-t2-n'), dados.get(f'{prefix}-t2-s')
            
            t1_id = get_or_create_team(n1)
            t2_id = get_or_create_team(n2)
            
            # Só salva se houver algo para salvar
            if t1_id or t2_id or (s1 and int(s1)>0) or (s2 and int(s2)>0):
                match_data = {
                    'tournament_id': tour_id, 'position_code': code,
                    'team1_id': t1_id, 'team2_id': t2_id,
                    'score1': int(s1) if s1 else 0, 'score2': int(s2) if s2 else 0
                }
                existing = supabase.table('matches').select('id').eq('tournament_id', tour_id).eq('position_code', code).execute()
                if existing.data:
                    supabase.table('matches').update(match_data).eq('id', existing.data[0]['id']).execute()
                else:
                    supabase.table('matches').insert(match_data).execute()

        return jsonify({"msg": "Salvo com sucesso!"})
    except Exception as e:
        print(e)
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
