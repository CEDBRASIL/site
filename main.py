from flask import Flask, request, jsonify
import requests, os, json
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

app = Flask(__name__)

# ───────────────────────── CONFIG ───────────────────────── #

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

OM_BASE_URL  = "https://meuappdecursos.com.br/ws/v2"
BASIC_B64    = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"
UNIDADE_ID   = 4158
TOKEN_URL    = f"{OM_BASE_URL}/unidades/token/{UNIDADE_ID}"
BASIC_KEY_RAW = "e6fc583511b1b88c34bd2a2610248a8c"
TOKEN_UNIDADE = None

CHATPRO_URL   = "https://v5.chatpro.com.br/chatpro-2a6ajg7xtk/send-message"
CHATPRO_TOKEN = "e10f158f102cd06bb3e8f135e159dd0f"

DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/"
    "1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"
)

USUARIOS_FILE = os.path.join(os.path.dirname(__file__), "usuarios.json")

# ───────────────────── FUNÇÕES AUXILIARES ───────────────────── #

def log_discord(msg: str):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except Exception:
        pass  # se Discord falhar, não interrompe o fluxo

def carregar_contador() -> int:
    if not os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, "w") as f:
            json.dump({"last_seq": 0}, f)
    with open(USUARIOS_FILE) as f:
        return json.load(f).get("last_seq", 0)

def salvar_contador(seq: int):
    with open(USUARIOS_FILE, "w") as f:
        json.dump({"last_seq": seq}, f)

def gerar_usuario() -> str:
    seq = carregar_contador() + 1
    salvar_contador(seq)
    return f"202500{seq}{UNIDADE_ID}"

def obter_token_unidade():
    global TOKEN_UNIDADE
    try:
        r = requests.get(TOKEN_URL, auth=HTTPBasicAuth(BASIC_KEY_RAW, ""))
        data = r.json()
        if data.get("status") == "true":
            TOKEN_UNIDADE = data["data"]["token"]
            log_discord("🔁 Token renovado.")
        else:
            log_discord(f"❌ Falha token: {data}")
    except Exception as e:
        log_discord(f"❌ Exceção token: {e}")

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
            for _id in f.get("value", []):
                nome = mapear_id_para_nome(_id, f.get("options", []))
                if nome:
                    nomes.append(nome)
    return list(set(nomes))

def ids_planos(cursos):
    ids = []
    for n in cursos:
        ids.extend(CURSO_PLANO_MAP.get(n, []))
    return list(set(ids))

def enviar_whatsapp(numero_br12, msg):
    headers = {
        "Authorization": f"Bearer {CHATPRO_TOKEN}",
        "Content-Type": "application/json",
    }
    requests.post(CHATPRO_URL, json={"phone": numero_br12, "message": msg}, headers=headers)

# ───────────────────────── ENDPOINTS ───────────────────────── #

@app.route("/secure", methods=["GET", "HEAD"])
def secure():
    obter_token_unidade()
    return "🛡️ Secure OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.json
        log_discord(f"📥 Webhook:\n```json\n{json.dumps(payload)[:1500]}```")

        if payload.get("eventType") != "FORM_RESPONSE":
            return jsonify({"msg": "ignorado"}), 200

        fields    = payload["data"]["fields"]
        nome      = extrair_valor(fields, "Seu nome completo")
        whatsapp  = extrair_valor(fields, "Whatsapp")

        if not (nome and whatsapp):
            log_discord("❌ Nome ou WhatsApp ausentes")
            return jsonify({"erro": "dados incompletos"}), 400

        cursos_nomes = coletar_cursos(fields)
        planos_ids   = ids_planos(cursos_nomes)
        if not planos_ids:
            log_discord("❌ Cursos não mapeados")
            return jsonify({"erro": "cursos inválidos"}), 400

        usuario = gerar_usuario()
        email_ficticio = f"{usuario}@cedbrasil.com"

        cadastro = {
            "token": TOKEN_UNIDADE,
            "nome": nome,
            "usuario": usuario,
            "senha": "123456",
            "email": email_ficticio,
            "doc_cpf": "",
            "fone": whatsapp,
            "celular": whatsapp,
            "pais": "Brasil",       # ← CAMPO OBRIGATÓRIO ATENDIDO
            "unidade_id": UNIDADE_ID,
            "cursos": ",".join(map(str, planos_ids)),
        }

        headers_basic = {"Authorization": f"Basic {BASIC_B64}"}

        resp = requests.post(f"{OM_BASE_URL}/alunos", data=cadastro, headers=headers_basic)

        try:
            data = resp.json()
        except Exception:
            log_discord(f"❌ Resposta não JSON: {resp.text}")
            return jsonify({"erro": "resposta inválida"}), 500

        if not (resp.ok and data.get("status") == "true"):
            log_discord(f"❌ Falha cadastro: {resp.text}")
            return jsonify({"erro": "cadastro falhou"}), 500

        # WhatsApp
        numero = "55" + "".join(filter(str.isdigit, whatsapp))[-11:]
        data_pagto = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
        lista_cursos = "\n".join(f"• {c}" for c in cursos_nomes)

        mensagem = (
            f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
            f"🔑 *Acesso*\nLogin: *{usuario}*\nSenha: *123456*\n\n"
            f"📚 *Cursos adquiridos:*\n{lista_cursos}\n\n"
            f"💳 *Data de pagamento:* {data_pagto}\n\n"
            "🧑‍🏫 *Grupo da sala:* https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP"
        )

        enviar_whatsapp(numero, mensagem)
        log_discord(f"✅ Usuário {usuario} matriculado e notificado.")

        return jsonify({"status": "ok", "usuario": usuario}), 200

    except Exception as e:
        log_discord(f"❌ Exceção: {e}")
        return jsonify({"erro": "exceção"}), 500

# ───────────────────────── MAIN ───────────────────────── #
if __name__ == "__main__":
    obter_token_unidade()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
