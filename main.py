"""
main.py – Webhook Tally → Cadastro/Matrícula, WhatsApp e Logs
• CPF é login do aluno
• Cria e matricula aluno via Ouro Moderno (Basic Auth + form data)
• Envia boas-vindas pelo ChatPro
• /secure renova token da unidade a cada 5 min
• Tudo logado no Discord
"""

from flask import Flask, request, jsonify
import requests, json, os
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

app = Flask(__name__)

#───────────────────────── CONFIG ─────────────────────────#

CURSO_PLANO_MAP = {
    "Excel PRO": [161, 197, 201],
    "Design Gráfico": [254, 751, 169],
    "Analise & Desenvolvimento de Sistemas": [590, 176, 239, 203],
    "Administração": [129, 198, 156, 154],
    "Inglês Fluente": [263, 280, 281],
    "Inglês Kids": [266],
    "Informática Essencial": [130, 599, 161, 160, 162],
    "Operador de Micro": [130, 599, 161, 160, 162],
    "Especialista em Marketing & Vendas": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734],
}

OURO_BASE_URL   = "https://meuappdecursos.com.br/ws/v2"
BASIC_AUTH_B64  = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"  # usuario:senha(base64); senha é vazia
UNIDADE_ID      = 4158

# Endpoint para renovar token da unidade
TOKEN_ENDPOINT  = f"{OURO_BASE_URL}/unidades/token/{UNIDADE_ID}"
BASIC_KEY_RAW   = "e6fc583511b1b88c34bd2a2610248a8c"  # passa como user, senha vazia
TOKEN_UNIDADE   = None

# ChatPro
CHATPRO_URL  = "https://v5.chatpro.com.br/chatpro-2a6ajg7xtk/send-message"
CHATPRO_TOKEN = "e10f158f102cd06bb3e8f135e159dd0f"

# Discord
DISCORD_WEBHOOK = ("https://discord.com/api/webhooks/"
                   "1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj")

#──────────────────── FUNÇÕES AUXILIARES ────────────────────#

def log_discord(msg: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except Exception as e:
        print("Log Discord falhou:", e)

def obter_token_unidade():
    """Renova TOKEN_UNIDADE via BasicAuth (user=BASIC_KEY_RAW, pass='')"""
    global TOKEN_UNIDADE
    try:
        r = requests.get(TOKEN_ENDPOINT, auth=HTTPBasicAuth(BASIC_KEY_RAW, ""))
        data = r.json()
        if data.get("status") == "true":
            TOKEN_UNIDADE = data["data"]["token"]
            log_discord("🔁 Token da unidade atualizado.")
        else:
            log_discord(f"❌ Falha ao obter token: {data}")
    except Exception as e:
        log_discord(f"❌ Exceção token: {e}")

def extrair_valor(fields, label):
    for f in fields:
        if f.get("label") == label:
            return f.get("value")
    return None

def map_id_to_name(opt_id, opts):
    for o in opts:
        if o["id"] == opt_id:
            return o["text"]
    return None

def coletar_cursos(fields):
    nomes = []
    for f in fields:
        if f["type"] == "MULTIPLE_CHOICE" and "Curso" in f["label"]:
            for _id in f.get("value", []):
                nome = map_id_to_name(_id, f.get("options", []))
                if nome:
                    nomes.append(nome)
    return list(set(nomes))

def planos_from(nomes):
    ids = []
    for n in nomes:
        ids.extend(CURSO_PLANO_MAP.get(n, []))
    return list(set(ids))

def enviar_whatsapp(numero_br12, msg):
    headers = {"Authorization": f"Bearer {CHATPRO_TOKEN}",
               "Content-Type": "application/json"}
    requests.post(CHATPRO_URL, json={"phone": numero_br12, "message": msg},
                  headers=headers)

#───────────────────────── ENDPOINTS ───────────────────────#

@app.route("/secure", methods=["GET", "HEAD"])
def secure():
    obter_token_unidade()
    return "🔐 Secure OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.json
        log_discord(f"📥 Webhook:\n```json\n{json.dumps(payload)[:1500]}```")

        if payload.get("eventType") != "FORM_RESPONSE":
            return jsonify({"msg": "evento ignorado"}), 200

        fields = payload["data"]["fields"]
        nome      = extrair_valor(fields, "Seu nome completo")
        whatsapp  = extrair_valor(fields, "Whatsapp")
        cpf       = str(extrair_valor(fields, "CPF"))
        if not (nome and whatsapp and cpf):
            log_discord("❌ Nome, CPF ou WhatsApp ausentes")
            return jsonify({"erro": "dados incompletos"}), 400

        cursos_nomes = coletar_cursos(fields)
        planos_ids   = planos_from(cursos_nomes)
        if not planos_ids:
            log_discord("❌ Cursos não mapeados")
            return jsonify({"erro": "cursos inválidos"}), 400

        # Payload form-urlencoded exigido pelo Ouro Moderno
        cadastro = {
            "token": TOKEN_UNIDADE,
            "nome": nome,
            "usuario": cpf,
            "senha": "123456",
            "doc_cpf": cpf,
            "fone": whatsapp,
            "celular": whatsapp,
            "unidade_id": UNIDADE_ID,
            "cursos": ",".join(map(str, planos_ids)),
            "data_nascimento": "",
            "email": "",
            "cep": "",
            "endereco": "",
            "numero": "",
            "complemento": "",
            "bairro": "",
            "cidade": "",
            "estado": "",
            "observacao": "",
            "data_matricula": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": "",
            "status": "1",  # 1 = ativo
            "tipo": "1",  # 1 = aluno
            "forma_pagamento": "1",  # 1 = à vista
            "valor": "0.00",  # valor zero, pois não é necessário
            "data_vencimento": "",
            "data_pagamento": "",
            "data_cancelamento": "",
            "motivo_cancelamento": "",
            "data_reativacao": "",
            "motivo_reativacao": "",
            "data_exclusao": "",
            "motivo_exclusao": "",
            "data_conclusao": "",
            "motivo_conclusao": "",
            "data_transferencia": "",
            "doc_rg": "",
        }

        headers_basic = {"Authorization": f"Basic {BASIC_AUTH_B64}"}

        resp = requests.post(f"{OURO_BASE_URL}/alunos",
                             data=cadastro,
                             headers=headers_basic)

        if resp.ok and resp.json().get("status") == "true":
            log_discord(f"✅ Aluno {nome} criado/matriculado.")
        else:
            log_discord(f"❌ Falha cadastro: {resp.text}")
            return jsonify({"erro": "cadastro falhou"}), 500

        # WhatsApp
        numero = "55" + "".join(filter(str.isdigit, whatsapp))[-11:]
        data_pagto = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
        lista = "\n".join(f"• {c}" for c in cursos_nomes)

        msg = (f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
               f"🔑 *Acesso*\nLogin: *{cpf}*\nSenha: *123456*\n\n"
               f"📚 *Cursos adquiridos:*\n{lista}\n\n"
               f"💳 *Data de pagamento:* {data_pagto}\n\n"
               "🧑‍🏫 *Grupo da sala:* https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP")

        enviar_whatsapp(numero, msg)
        log_discord(f"📤 WhatsApp enviado para {numero}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        log_discord(f"❌ Exceção: {e}")
        return jsonify({"erro": "exceção"}), 500

#───────────────────────── MAIN ───────────────────────────#

if __name__ == "__main__":
    obter_token_unidade()  # tenta logo ao subir
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
