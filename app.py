import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
# Permite que seu site no Hostgator fale com este servidor
CORS(app, resources={r"/*": {"origins": "*"}})

# Pega as senhas que vamos configurar no painel do Render
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

# Conecta ao Banco de Dados
if url and key:
    supabase: Client = create_client(url, key)
else:
    print("ERRO: Variáveis SUPABASE_URL ou SUPABASE_KEY não encontradas.")

@app.route('/')
def home():
    return "Backend do Torneio está ON! 🚀"

# 1. ROTA PARA LER (Seu site pede dados aqui)
@app.route('/api/torneio/<jogo_id>', methods=['GET'])
def get_torneio(jogo_id):
    try:
        response = supabase.table('torneios').select("*").eq('id', jogo_id).execute()
        # O supabase-py retorna um objeto com .data
        if response.data and len(response.data) > 0:
            return jsonify(response.data[0]['dados'])
        else:
            return jsonify({}) # Retorna vazio se não tiver nada salvo
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# 2. ROTA PARA SALVAR (Seu painel admin manda dados pra cá)
@app.route('/api/torneio', methods=['POST'])
def save_torneio():
    try:
        conteudo = request.json
        jogo_id = conteudo.get('jogo_id')
        dados = conteudo.get('dados')

        item = {
            "id": jogo_id,
            "dados": dados
        }
        
        # Upsert = Cria ou Atualiza
        supabase.table('torneios').upsert(item).execute()
        return jsonify({"mensagem": "Salvo com sucesso!"})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)