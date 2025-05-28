from flask import Flask, request, jsonify
import requests, json, re, threading, time
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)

# ───────────── CONFIGURAÇÕES ───────────── #
CURSO_PLANO_MAP = {
    "Excel PRO": [161, 197, 201],
    "Desigh Gráfico": [254, 751, 169],
    "Analise & Desenvolvimento de Sistemas": [590, 176, 239, 203],
    "Administração": [129, 198, 156, 154],
    "Inglês Fluente": [263, 280, 281],
    "Inglês Kids": [266],
    "Informática Essencial": [130, 599, 161, 160, 162],
    "Operador de Micro": [130, 599, 161, 160, 162],
    "Especialista em Marketing & Vendas": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734],
    "Operador de Micro": [123, 414]
}

OM_BASE       = os.getenv("OM_BASE")
UNIDADE_ID    = int(os.getenv("UNIDADE_ID"))
TOKEN_KEY     = os.getenv("TOKEN_KEY")
BASIC_B64     = os.getenv("BASIC_B64")
CHATPRO_URL   = os.getenv("CHATPRO_URL")
CHATPRO_TOKEN = os.getenv("CHATPRO_TOKEN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

token_unidade = None
processed_ids = set()

# ───────────── AUXILIARES ───────────── #
def log(msg):
    print(msg)
    try: requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except: pass

def renovar_token():
    global token_unidade
    url = f"{OM_BASE}/unidades/token/{UNIDADE_ID}"
    r = requests.get(url, auth=HTTPBasicAuth(TOKEN_KEY, ""))
    log(f"[TOKEN] {r.status_code} {r.text}")
    if r.ok and r.json().get("status") == "true":
        token_unidade = r.json()["data"]["token"]
        log("🔁 Token renovado")
    else:
        log("❌ Falha ao renovar token")

def coletar(fields, label_sub):
    nomes = []
    for f in fields:
        if f.get("type") == "MULTIPLE_CHOICE" and label_sub in f.get("label", ""):
            for vid in f.get("value") or []:
                texto = next((o["text"] for o in f.get("options", []) if o["id"] == vid), None)
                if texto: nomes.append(texto)
    return nomes

def map_ids(names):
    ids = []
    for n in names:
        ids += CURSO_PLANO_MAP.get(n.strip(), [])
    return list(set(ids))

def send_whatsapp(num, msg):
    h = {"Authorization": CHATPRO_TOKEN, "Content-Type": "application/json", "accept": "application/json"}
    p = {"number": num, "message": msg}
    try:
        r = requests.post(CHATPRO_URL, json=p, headers=h)
        log(f"[WHATSAPP] {num} {r.status_code} {r.text}")
    except Exception as e:
        log(f"❌ Erro WhatsApp: {e}")

# ───────────── LÓGICA DE PROCESSAMENTO ───────────── #
def processar_dados(payload):
    time.sleep(5)  # Aguarda o servidor estar 100% ativo

    rid = payload["data"].get("responseId")
    if rid in processed_ids:
        log(f"[PROCESSAMENTO] Ignorado duplicado: {rid}")
        return
    processed_ids.add(rid)

    fields   = payload["data"]["fields"]
    nome     = next((v["value"] for v in fields if v["label"]=="Seu nome completo"), "").strip()
    whatsapp = next((v["value"] for v in fields if v["label"]=="Whatsapp"), "").strip()
    cpf      = str(next((v["value"] for v in fields if v["label"]=="CPF"), "")).zfill(11)

    if not all([nome, whatsapp, cpf]):
        log("❌ Dados obrigatórios ausentes")
        return

    cursos_desejados = coletar(fields, "Curso Desejado")
    if not cursos_desejados:
        log("❌ Curso Desejado obrigatório")
        return
    cursos_extras = coletar(fields, "Curso extra")
    cursos = cursos_desejados + cursos_extras
    log(f"[CURSOS] {cursos}")

    planos = map_ids(cursos)
    if not planos:
        log("❌ Cursos não mapeados")
        return

    renovar_token()

    cadastro = {
        "token": token_unidade,
        "nome": nome,
        "usuario": cpf,
        "senha": "123456",
        "email": f"{cpf}@ced.com",
        "doc_cpf": cpf,
        "doc_rg": "0000000",
        "data_nascimento": "01/01/2000",
        "pais": "Brasil",
        "uf": "DF",
        "cidade": "",
        "bairro": "",
        "endereco": "",
        "numero": "",
        "complemento": "",
        "cep": "",
        "fone": whatsapp,
        "celular": whatsapp,
        "unidade_id": UNIDADE_ID
    }

    r = requests.post(f"{OM_BASE}/alunos", data=cadastro, headers={"Authorization":f"Basic {BASIC_B64}"})
    log(f"[CADASTRO] {r.status_code} {r.text}")
    if not (r.ok and r.json().get("status")=="true"):
        log("❌ Falha no cadastro")
        return

    aluno_id = r.json()["data"]["id"]
    matricula = {"token": token_unidade, "cursos": ",".join(map(str, planos))}
    rm = requests.post(f"{OM_BASE}/alunos/matricula/{aluno_id}", data=matricula,
                       headers={"Authorization":f"Basic {BASIC_B64}"})
    log(f"[MATRICULA] {rm.status_code} {rm.text}")
    if not (rm.ok and rm.json().get("status")=="true"):
        log("❌ Falha na matrícula")
        return

    numero = "55" + "".join(re.findall(r"\d", whatsapp))[-11:]
    vence  = (datetime.now()+timedelta(days=5)).strftime("%d/%m/%Y")
    lista  = "\n".join(f"• {c}" for c in cursos)

    msg = (
        f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
        f"🔑 *Acesso*\nLogin: *{cpf}*\nSenha: *123456*\n\n"
        f"📚 *Cursos Adquiridos:* \n{lista}\n\n"
        f"💳 *Data de pagamento:* {vence}\n\n"
        "🧑‍🏫 *Grupo Da Escola:* https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP\n\n"
        "📱 *Acesse pelo seu dispositivo preferido:*\n"
        "• *Android:* https://play.google.com/store/apps/details?id=br.com.om.app&hl=pt\n\n"
        "• *iOS:* https://apps.apple.com/fr/app/meu-app-de-cursos/id1581898914\n\n"
        "• *Computador:* https://ead.cedbrasilia.com.br/\n\n"
        "Caso você queira trocar ou adicionar outros cursos, entre em contato conosco por esse número!\n\n"
        "Obrigado por escolher a CED Cursos! Estamos aqui para ajudar você a alcançar seus objetivos educacionais. \n\n"
        "Atenciosamente, *Equipe CED*"
    )
    send_whatsapp(numero, msg)

# ───────────── ROTAS ───────────── #
@app.route("/secure")
def secure():
    renovar_token()
    return "ok", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json
    log(f"[WEBHOOK] {json.dumps(payload)[:1000]}")

    if payload.get("eventType") != "FORM_RESPONSE":
        return jsonify({"msg":"ignorado"}), 200

    threading.Thread(target=processar_dados, args=(payload,)).start()
    return jsonify({"msg":"recebido"}), 200

if __name__=="__main__":
    renovar_token()
    app.run(host="0.0.0.0", port=5000)
