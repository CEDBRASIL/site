from flask import Flask, request, jsonify
import requests, json, re
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta

app = Flask(__name__)

# ───────────── CONFIGURAÇÕES ───────────── #
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

OM_BASE       = "https://meuappdecursos.com.br/ws/v2"
UNIDADE_ID    = 4158
TOKEN_KEY     = "e6fc583511b1b88c34bd2a2610248a8c"
BASIC_B64     = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"

CHATPRO_URL   = "https://v5.chatpro.com.br/chatpro-2a6ajg7xtk/api/v1/send_message"
CHATPRO_TOKEN = "e10f158f102cd06bb3e8f135e159dd0f"

DISCORD_WEBHOOK = (
    "https://discord.com/api/webhooks/"
    "1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"
)

processed_ids   = set()
token_unidade   = None

# ───────────── AUXILIARES ───────────── #
def log(msg):
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except:
        pass

def renovar_token():
    global token_unidade
    url = f"{OM_BASE}/unidades/token/{UNIDADE_ID}"
    r = requests.get(url, auth=HTTPBasicAuth(TOKEN_KEY, ""))
    if r.ok and r.json().get("status") == "true":
        token_unidade = r.json()["data"]["token"]
        log("🔁 Token renovado")
    else:
        log(f"❌ Falha ao renovar token: {r.text}")

def coletar(fields, label_sub):
    nomes = []
    for f in fields:
        if f.get("type") == "MULTIPLE_CHOICE" and label_sub in f.get("label", ""):
            values = f.get("value") or []
            for vid in values:
                texto = next((o["text"] for o in f.get("options", []) if o["id"] == vid), None)
                if texto:
                    nomes.append(texto)
    return nomes

def map_ids(names):
    ids = []
    for n in names:
        ids += CURSO_PLANO_MAP.get(n.strip(), [])
    return list(set(ids))

def send_whatsapp(num, msg):
    headers = {
        "Authorization": CHATPRO_TOKEN,
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    payload = {"number": num, "message": msg}
    try:
        r = requests.post(CHATPRO_URL, json=payload, headers=headers)
        log(f"📤 WhatsApp para {num}: {r.status_code} {r.text}")
    except Exception as e:
        log(f"❌ Erro no WhatsApp para {num}: {e}")

# ───────────── ROTAS ───────────── #
@app.route("/secure")
def secure():
    renovar_token()
    return "ok", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json
    if payload.get("eventType") != "FORM_RESPONSE":
        return jsonify({"msg": "ignorado"}), 200

    rid = payload["data"].get("responseId")
    if rid in processed_ids:
        return jsonify({"msg": "duplicado"}), 200
    processed_ids.add(rid)

    fields    = payload["data"]["fields"]
    nome      = next((v["value"] for v in fields if v["label"] == "Seu nome completo"), "").strip()
    whatsapp  = next((v["value"] for v in fields if v["label"] == "Whatsapp"), "").strip()
    cpf       = str(next((v["value"] for v in fields if v["label"] == "CPF"), "")).zfill(11)

    if not all([nome, whatsapp, cpf]):
        return jsonify({"erro": "Campos obrigatórios ausentes"}), 400

    # Coleta cursos
    cursos_desejados = coletar(fields, "Curso Desejado")
    cursos_extras    = coletar(fields, "Curso extra")
    if not cursos_desejados:
        return jsonify({"erro": "Curso Desejado é obrigatório"}), 400

    cursos = cursos_desejados + cursos_extras
    planos = map_ids(cursos)
    if not planos:
        return jsonify({"erro": "Cursos não mapeados"}), 400

    renovar_token()

    # Campos fixos obrigatórios
    data_nascimento = "01/01/2000"
    doc_rg          = "0000000"  # valor padrão

    cadastro = {
        "token": token_unidade,
        "nome": nome,
        "usuario": cpf,
        "senha": "123456",
        "email": f"{cpf}@ced.com",
        "doc_cpf": cpf,
        "doc_rg": doc_rg,
        "data_nascimento": data_nascimento,
        "pais": "Brasil",
        "fone": whatsapp,
        "celular": whatsapp,
        "unidade_id": UNIDADE_ID
    }

    # Cadastro
    r = requests.post(f"{OM_BASE}/alunos", data=cadastro, headers={"Authorization": f"Basic {BASIC_B64}"})
    if not (r.ok and r.json().get("status") == "true"):
        log(f"❌ Erro no cadastro: {r.text}")
        return jsonify({"erro": "Falha ao cadastrar"}), 500

    aluno_id = r.json()["data"]["id"]

    # Matrícula
    matricula = {"token": token_unidade, "cursos": ",".join(map(str, planos))}
    rm = requests.post(f"{OM_BASE}/alunos/matricula/{aluno_id}", data=matricula,
                       headers={"Authorization": f"Basic {BASIC_B64}"})
    if not (rm.ok and rm.json().get("status") == "true"):
        log(f"❌ Erro na matrícula: {rm.text}")
        return jsonify({"erro": "Falha na matrícula"}), 500

    # Envio WhatsApp
    numero = "55" + "".join(re.findall(r"\d", whatsapp))[-11:]
    venc   = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
    lista  = "\n".join(f"• {c}" for c in cursos)

    msg = (
        f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
        f"🔑 *Acesso*\nLogin: *{cpf}*\nSenha: *123456*\n\n"
        f"📚 *Cursos:* \n{lista}\n\n"
        f"💳 *Data de pagamento:* {venc}\n\n"
        "🧑‍🏫 *Grupo:* https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP"
    )
    send_whatsapp(numero, msg)

    log(f"✅ {cpf} cadastrado e matriculado em: {lista}")
    return jsonify({"status": "ok", "usuario": cpf}), 200

if __name__ == "__main__":
    renovar_token()
    app.run(host="0.0.0.0", port=5000)
