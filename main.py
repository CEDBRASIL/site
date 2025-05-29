#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CED · Webhook de matrícula automática
Versão 29-mai-2025
"""

import os, json, re, threading, time, requests, traceback
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ───────────── CARREGA .env ───────────── #
load_dotenv()
OM_BASE          = os.getenv("OM_BASE")
UNIDADE_ID       = int(os.getenv("UNIDADE_ID"))
TOKEN_KEY        = os.getenv("TOKEN_KEY")
BASIC_B64        = os.getenv("BASIC_B64")
CHATPRO_URL      = os.getenv("CHATPRO_URL")
CHATPRO_TOKEN    = os.getenv("CHATPRO_TOKEN")
DISCORD_WEBHOOK  = os.getenv("DISCORD_WEBHOOK")

app           = Flask(__name__)
token_unidade = None
processed_ids = set()
cpf_lock      = threading.Lock()

# ───────────── CURSOS → PLANOS ───────────── #
CURSO_PLANO_MAP = {
    "Excel PRO":                          [161, 197, 201],
    "Desigh Gráfico":                     [254, 751, 169],
    "Analise & Desenvolvimento de Sistemas": [590, 176, 239, 203],
    "Administração":                      [129, 198, 156, 154],
    "Inglês Fluente":                     [263, 280, 281],
    "Inglês Kids":                        [266],
    "Informática Essencial":              [130, 599, 161, 160, 162],
    "Especialista em Marketing & Vendas": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734],
}

# ───────────── FUNÇÕES AUXILIARES ───────────── #
def log(msg: str):
    print(msg)
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg[:1900]})
    except:
        pass

def renovar_token():
    global token_unidade
    url = f"{OM_BASE}/unidades/token/{UNIDADE_ID}"
    r   = requests.get(url, auth=HTTPBasicAuth(TOKEN_KEY, ""))
    log(f"[TOKEN] {r.status_code} {r.text}")
    if r.ok and r.json().get("status") == "true":
        token_unidade = r.json()["data"]["token"]
        log("🔁 Token renovado")
    else:
        log("❌ Falha ao renovar token")

def coletar(fields: list, label_sub: str) -> list:
    nomes = []
    for f in fields:
        if f.get("type") == "MULTIPLE_CHOICE" and label_sub in f.get("label", ""):
            for vid in f.get("value") or []:
                texto = next((o["text"] for o in f.get("options", []) if o["id"] == vid), None)
                if texto:
                    nomes.append(texto)
    return nomes

def map_ids(names: list) -> list[int]:
    ids = []
    for n in names:
        ids += CURSO_PLANO_MAP.get(n.strip(), [])
    return list(set(ids))

def send_whatsapp(num: str, msg: str):
    h = {"Authorization": CHATPRO_TOKEN,
         "Content-Type": "application/json",
         "accept": "application/json"}
    p = {"number": num, "message": msg}
    try:
        r = requests.post(CHATPRO_URL, json=p, headers=h)
        log(f"[WHATSAPP] {num} {r.status_code} {r.text}")
    except Exception as e:
        log(f"❌ Erro WhatsApp: {e}")

# ───────────── GERAÇÃO AUTOMÁTICA DE CPF ───────────── #
CPF_PREFIXO = "20254158"

def total_alunos() -> int:
    url = f"{OM_BASE}/alunos/total/{UNIDADE_ID}"
    r   = requests.get(url, headers={"Authorization": f"Basic {BASIC_B64}"})
    if r.ok and r.json().get("status") == "true":
        return int(r.json()["data"]["total"])
    # fallback
    url = f"{OM_BASE}/alunos?unidade_id={UNIDADE_ID}&cpf_like={CPF_PREFIXO}"
    r   = requests.get(url, headers={"Authorization": f"Basic {BASIC_B64}"})
    if r.ok and r.json().get("status") == "true":
        return len(r.json()["data"])
    raise RuntimeError("Não foi possível obter o total de alunos.")

def proximo_cpf(incremento: int = 0) -> str:
    """
    Gera CPF sequencial com opção de incrementar manualmente.
    """
    with cpf_lock:
        seq = total_alunos() + 1 + incremento
        return CPF_PREFIXO + str(seq).zfill(3)

# ───────────── FUNÇÃO DE CADASTRO COM RETENTATIVA ───────────── #
def cadastrar_aluno(cadastro_base: dict, tentativas: int = 60) -> tuple[int|None, str|None]:
    """
    Tenta cadastrar o aluno até 'tentativas' vezes.
    Se encontrar login duplicado, incrementa o CPF e tenta novamente.
    Retorna (aluno_id, cpf_efetivo) ou (None, None) em caso de falha.
    """
    for i in range(tentativas):
        cadastro = cadastro_base.copy()
        if i > 0:
            # Incrementa CPF/usuário
            novo_cpf = str(int(cadastro["usuario"]) + 1).zfill(len(cadastro["usuario"]))
            cadastro["usuario"] = novo_cpf
            cadastro["doc_cpf"] = novo_cpf
            cadastro["email"]  = f"{novo_cpf}@ced.com"

        r = requests.post(f"{OM_BASE}/alunos", data=cadastro,
                          headers={"Authorization": f"Basic {BASIC_B64}"})
        log(f"[CADASTRO] tentativa {i+1}/{tentativas} | {r.status_code} {r.text}")

        if r.ok and r.json().get("status") == "true":
            return r.json()["data"]["id"], cadastro["usuario"]

        # Se a mensagem não fala em duplicidade, não adianta tentar de novo
        info = (r.json() or {}).get("info", "").lower()
        if "já está em uso" not in info:
            break

    log("❌ Falha no cadastro após tentativas")
    return None, None

# ───────────── PROCESSAMENTO DE INSCRIÇÃO ───────────── #
def processar_dados(payload: dict):
    time.sleep(5)  # cold start
    try:
        rid = payload["data"].get("responseId")
        if rid in processed_ids:
            log(f"[PROCESSAMENTO] Ignorado duplicado: {rid}")
            return
        processed_ids.add(rid)

        fields = payload["data"]["fields"]

        # Captura campos com checagem flexível nos labels
        nome     = next((v["value"] for v in fields if "nome" in v["label"].lower()), "").strip()
        whatsapp = next((v["value"] for v in fields if "whats" in v["label"].lower()), "").strip()
        cpf_val  = next((v["value"] for v in fields if "cpf"  in v["label"].lower()), "")
        cpf_raw  = str(cpf_val).strip()
        cpf      = cpf_raw.zfill(11) if cpf_raw else proximo_cpf()

        if not all([nome, whatsapp]):
            log("❌ Dados obrigatórios ausentes (nome ou whatsapp)")
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

        cadastro_modelo = {
            "token":             token_unidade,
            "nome":              nome,
            "usuario":           cpf,
            "senha":             "123456",
            "email":             f"{cpf}@ced.com",
            "doc_cpf":           cpf,
            "doc_rg":            "0000000",
            "data_nascimento":   "01/01/2000",
            "pais":              "Brasil",
            "uf":                "DF",
            "cidade":            "",
            "bairro":            "",
            "endereco":          "",
            "numero":            "",
            "complemento":       "",
            "cep":               "",
            "fone":              whatsapp,
            "celular":           whatsapp,
            "unidade_id":        UNIDADE_ID
        }

        aluno_id, cpf_final = cadastrar_aluno(cadastro_modelo)
        if not aluno_id:
            return  # Falha já logada em cadastrar_aluno()

        # ---------- Matrícula ----------
        matricula = {"token": token_unidade,
                     "cursos": ",".join(map(str, planos))}
        rm = requests.post(f"{OM_BASE}/alunos/matricula/{aluno_id}", data=matricula,
                           headers={"Authorization": f"Basic {BASIC_B64}"})
        log(f"[MATRICULA] {rm.status_code} {rm.text}")
        if not (rm.ok and rm.json().get("status") == "true"):
            log("❌ Falha na matrícula")
            return

        # ---------- WhatsApp ----------
        numero = "55" + "".join(re.findall(r"\d", whatsapp))[-11:]
        lista  = "\n".join(f"• {c}" for c in cursos)
        data_pagamento = (datetime.now() + timedelta(days=5)).strftime("%d/%m/%Y")
        msg = (
            f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
            f"🔑 *Acesso*\nLogin: *{cpf_final}*\nSenha: *123456*\n\n"
            f"📚 *Cursos Adquiridos:* \n{lista}\n\n"
            f"💳 *Data de pagamento:* *{data_pagamento}*\n\n"
            "🧑‍🏫 *Grupo da Escola:* https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP\n\n"
            "📱 *Acesse pelo seu dispositivo preferido:*\n"
            "• *Android:* https://play.google.com/store/apps/details?id=br.com.om.app&hl=pt\n"
            "• *iOS:* https://apps.apple.com/fr/app/meu-app-de-cursos/id1581898914\n"
            "• *Computador:* https://ead.cedbrasilia.com.br/\n\n"
            "Caso deseje trocar ou adicionar outros cursos, basta responder a esta mensagem.\n\n"
            "Obrigado por escolher a *CED Cursos*! Estamos aqui para ajudar nos seus objetivos educacionais.\n\n"
            "Atenciosamente, *Equipe CED*"
        )
        send_whatsapp(numero, msg)

    except Exception as e:
        log(f"❌ Erro inesperado: {e}\n{traceback.format_exc()}")

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
        return jsonify({"msg": "ignorado"}), 200
    threading.Thread(target=processar_dados, args=(payload,)).start()
    return jsonify({"msg": "recebido"}), 200

if __name__ == "__main__":
    renovar_token()
    app.run(host="0.0.0.0", port=5000)
