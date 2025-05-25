from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import os, json

app = Flask(__name__)

# ───────────────────────── CONFIGURAÇÕES ───────────────────────── #

CURSO_PLANO_MAP = {
    "Excel PRO": [161, 197, 201],
    "Design Gráfico": [254, 751, 169],
    "Analise & Desenvolvimento de Sistemas": [590, 176, 239, 203],
    "Administração": [129, 198, 156, 154],
    "Inglês Fluente": [263, 280, 281],
    "Inglês Kids": [266],
    "Informática Essencial": [130, 599, 161, 160, 162],
    "Operador de Micro": [130, 599, 161, 160, 162],
    "Especialista em Marketing & Vendas": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734]
}

API_CADASTRO_URL = "https://meuappdecursos.com.br/ws/v2/alunos"
API_BASIC_TOKEN  = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"
UNIDADE_ID       = 4158
API_BEARER_TOKEN = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"
headers = {
    "Authorization": f"Basic {API_BASIC_TOKEN}",
    "Content-Type": "application/json"
}

TOKEN_ENDPOINT = "https://meuappdecursos.com.br/ws/v2/unidades/token"
BASIC_KEY      = "e6fc583511b1b88c34bd2a2610248a8c"
TOKEN_UNIDADE  = None

CHATPRO_ENDPOINT = "https://v5.chatpro.com.br/chatpro-2a6ajg7xtk/send-message"
CHATPRO_TOKEN    = "e10f158f102cd06bb3e8f135e159dd0f"

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"

# ───────────────────────── FUNÇÕES AUXILIARES ───────────────────────── #

def log_discord(msg: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except Exception as e:
        print("Falha log Discord:", e)

def obter_token_unidade():
    global TOKEN_UNIDADE
    try:
        url = f"{TOKEN_ENDPOINT}/{UNIDADE_ID}"
        r = requests.get(url, auth=HTTPBasicAuth(BASIC_KEY, ""))
        data = r.json()
        if data.get("status") == "true":
            TOKEN_UNIDADE = data["data"]["token"]
            log_discord("🔁 Token da unidade atualizado com sucesso.")
        else:
            log_discord(f"❌ Falha ao obter token: {data}")
    except Exception as e:
        log_discord(f"❌ Exceção ao obter token: {e}")

def extrair_valor(fields, label):
    for f in fields:
        if f.get("label") == label:
            return f.get("value")
    return None

def mapear_id_para_nome(opt_id, options):
    for op in options:
        if op["id"] == opt_id:
            return op["text"]
    return None

def coletar_cursos(fields):
    nomes = []
    for f in fields:
        if f["type"] == "MULTIPLE_CHOICE" and "Curso" in f["label"]:
            sel = f.get("value", [])
            options = f.get("options", [])
            for _id in sel:
                nome = mapear_id_para_nome(_id, options)
                if nome:
                    nomes.append(nome)
    return list(set(nomes))

def ids_planos(cursos):
    ids = []
    for n in cursos:
        ids.extend(CURSO_PLANO_MAP.get(n, []))
    return list(set(ids))

def enviar_whatsapp(numero_br12, mensagem):
    headers = {
        "Authorization": f"Bearer {CHATPRO_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(CHATPRO_ENDPOINT, json={"phone": numero_br12, "message": mensagem}, headers=headers)

# ───────────────────────── ENDPOINTS ───────────────────────── #

@app.route("/secure", methods=["GET", "HEAD"])
def secure():
    obter_token_unidade()
    return "🛡️ Secure ping OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.json
        log_discord(f"📥 Webhook recebido:\n```json\n{json.dumps(payload)[:1500]}```")

        if payload.get("eventType") != "FORM_RESPONSE":
            return jsonify({"msg": "Evento ignorado"}), 200

        fields    = payload["data"]["fields"]
        nome      = extrair_valor(fields, "Seu nome completo")
        whatsapp  = extrair_valor(fields, "Whatsapp")
        cpf       = str(extrair_valor(fields, "CPF"))
        email     = extrair_valor(fields, "E-mail")

        if not (nome and whatsapp and cpf and email):
            log_discord("❌ Nome/WhatsApp/CPF/E-mail ausentes")
            return jsonify({"erro": "Dados ausentes"}), 400

        cursos_nomes = coletar_cursos(fields)
        planos_ids   = ids_planos(cursos_nomes)
        if not planos_ids:
            log_discord("❌ Nenhum curso mapeado")
            return jsonify({"erro": "Cursos inválidos"}), 400

        cadastro = {
            "nome": nome,
            "usuario": cpf,
            "senha": "123456",
            "cpf": cpf,
            "email": email,
            "data_nascimento": "",
            "whatsapp": whatsapp,
            "planos": planos_ids,
            "unidade_id": UNIDADE_ID,
            "token": TOKEN_UNIDADE
        }

        headers = {
            "Authorization": f"Bearer {API_BEARER_TOKEN}",
            "Content-Type": "application/json"
        }

        resp = requests.post(API_CADASTRO_URL, json=cadastro, headers=headers)

        if resp.status_code not in (200, 201):
            log_discord(f"❌ Falha cadastro: {resp.text}")
            return jsonify({"erro": "Cadastro falhou"}), 500

        numero = "55" + "".join(filter(str.isdigit, whatsapp))[-11:]
        data_pagto = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
        lista_cursos = "\n".join(f"• {c}" for c in cursos_nomes)

        mensagem = (
            f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
            f"🔑 *Acesso*\n"
            f"Login: *{cpf}*\n"
            f"Senha: *123456*\n\n"
            f"📚 *Cursos adquiridos:*\n{lista_cursos}\n\n"
            f"💳 *Data de pagamento:* {data_pagto}\n\n"
            "🧑‍🏫 *Grupo da sala de aula:*\n"
            "https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP"
        )

        enviar_whatsapp(numero, mensagem)
        log_discord(f"✅ Aluno {nome} cadastrado, matriculado e notificado.")
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log_discord(f"❌ Exceção geral: {e}")
        return jsonify({"erro": "Exceção"}), 500

# ───────────────────────── MAIN ───────────────────────── #
if __name__ == "__main__":
    obter_token_unidade()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
