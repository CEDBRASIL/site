from flask import Flask
import requests
import json
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# Configurações da API Ouro Moderno
API_BASE_URL = "https://meuappdecursos.com.br/ws/v2"
API_KEY = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"  # Token da API
unidade_token = None  # Token da unidade (atualizado periodicamente)

# ID da unidade da escola
UNIDADE_ID = 4158

# Função para obter o token da unidade
def obter_token_unidade():
    global unidade_token
    url = f"{API_BASE_URL}/unidades/token/{UNIDADE_ID}"
    headers = {
        "Authorization": f"Basic {API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    response_data = response.json()
    if response.status_code == 200 and response_data.get("status") == "true":
        unidade_token = response_data["data"]["token"]
    else:
        # Log detalhado para diagnóstico
        enviar_log_discord(f"❌ Erro ao obter token da unidade: {response_data}, Status Code: {response.status_code}")
        raise Exception(f"Erro ao obter token da unidade: {response_data}")

# Função para enviar logs para o Discord
def enviar_log_discord(mensagem):
    webhook_url = "https://discord.com/api/webhooks/1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"
    payload = {"content": mensagem}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        if response.status_code != 204:
            print(f"Erro ao enviar log para o Discord: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Erro ao conectar ao Discord: {str(e)}")

# Endpoint para atualizar o token da unidade
@app.route('/secure', methods=['GET', 'HEAD'])
def secure_check():
    try:
        obter_token_unidade()
        mensagem = "🔐 Token atualizado com sucesso via /secure"
        enviar_log_discord(mensagem)
        return mensagem, 200
    except Exception as e:
        mensagem = f"Erro ao atualizar token: {str(e)}"
        enviar_log_discord(mensagem)
        return mensagem, 500

# Função para cadastrar aluno na API Ouro Moderno
def cadastrar_aluno(nome, whatsapp, cpf):
    url = f"{API_BASE_URL}/alunos"
    headers = {
        "Authorization": f"Bearer {unidade_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "nome": nome,
        "whatsapp": whatsapp,
        "cpf": cpf,
        "unidade_id": UNIDADE_ID
    }
    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    if response.status_code == 201:
        aluno_id = response_data["data"]["id"]  # Retorna o ID do aluno
        enviar_log_discord(f"✅ Aluno cadastrado com sucesso: {nome} (ID: {aluno_id})")
        return aluno_id
    else:
        enviar_log_discord(f"❌ Erro ao cadastrar aluno {nome}: {str(response_data)}")
        raise Exception(f"Erro ao cadastrar aluno: {response_data}")

# Função para matricular aluno em cursos
def matricular_aluno(aluno_id, curso_ids):
    url = f"{API_BASE_URL}/matriculas"
    headers = {
        "Authorization": f"Bearer {unidade_token}",
        "Content-Type": "application/json"
    }
    for curso_id in curso_ids:
        payload = {
            "aluno_id": aluno_id,
            "curso_id": curso_id
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 201:
            response_data = response.json()
            enviar_log_discord(f"❌ Erro ao matricular aluno {aluno_id} no curso {curso_id}: {str(response_data)}")
            raise Exception(f"Erro ao matricular aluno no curso {curso_id}: {response_data}")

# Função principal para processar o evento do Tally.so
def processar_evento_tally(evento):
    # Extrai os dados do evento
    nome = evento["data"]["fields"][0]["value"]
    whatsapp = evento["data"]["fields"][1]["value"]
    cpf = evento["data"]["fields"][2]["value"]
    cursos_desejados = evento["data"]["fields"][3]["value"]

    # Mapeia os cursos desejados para IDs da API Ouro Moderno
    with open("mapeamento dos cursos.txt", "r", encoding="utf-8") as f:
        mapeamento_cursos = json.loads(f.read().replace("\"", "\\\""))

    curso_ids = []
    for curso in cursos_desejados:
        for nome_curso, ids in mapeamento_cursos.items():
            if curso in nome_curso:
                curso_ids.extend(ids)

    # Cadastra o aluno
    aluno_id = cadastrar_aluno(nome, whatsapp, cpf)

    # Matricula o aluno nos cursos
    matricular_aluno(aluno_id, curso_ids)

# Exemplo de uso
if __name__ == "__main__":
    # Inicializa o token da unidade ao iniciar o servidor
    obter_token_unidade()
    with open("Eventlog.json", "r", encoding="utf-8") as f:
        evento = json.load(f)
    processar_evento_tally(evento)
    app.run(host="0.0.0.0", port=5000)