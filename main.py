"""
main.py – Webhook Tally → Cadastro & Matrícula + WhatsApp

• Recebe payload do Tally
• Cria aluno (CPF = usuário / login)
• Matricula nos cursos mapeados
• Envia mensagem de boas-vindas via ChatPro
"""

from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# ──────────────────── CONFIGURAÇÕES ──────────────────── #

# Mapeamento “Nome do curso” → lista de IDs (planos/módulos)
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

# Sua API interna
API_URL      = "https://suaapi.com.br/alunos"    # ajuste!
API_TOKEN    = "sua_chave_de_api"                # ajuste!
UNIDADE_ID   = 4158                              # ajuste!

# ChatPro
CHATPRO_ENDPOINT = "https://v5.chatpro.com.br/chatpro-2a6ajg7xtk/send-message"
CHATPRO_TOKEN    = "e10f158f102cd06bb3e8f135e159dd0f"

# ──────────────────── FUNÇÕES AUXILIARES ──────────────────── #

def extrair_por_label(fields, label):
    """Retorna o value de um campo pelo label"""
    for f in fields:
        if f.get("label") == label:
            return f.get("value")
    return None

def mapear_id_para_nome(id_opcao, field_options):
    for opt in field_options:
        if opt["id"] == id_opcao:
            return opt["text"]
    return None

def coletar_cursos(fields):
    """Retorna lista de nomes de cursos (principal + extra)"""
    nomes = []

    for f in fields:
        if f["type"] == "MULTIPLE_CHOICE" and "Curso" in f["label"]:
            ids_escolhidos = f.get("value", [])
            options = f.get("options", [])
            for opcao_id in ids_escolhidos:
                nome = mapear_id_para_nome(opcao_id, options)
                if nome:
                    nomes.append(nome)

    return list(set(nomes))  # remove duplicados

def ids_planos_de(cursos):
    """Retorna lista única de IDs de planos para os cursos dados"""
    ids = []
    for nome in cursos:
        ids.extend(CURSO_PLANO_MAP.get(nome, []))
    return list(set(ids))

def enviar_whatsapp(numero_br12, mensagem):
    """Envia mensagem via ChatPro"""
    payload = {"phone": numero_br12, "message": mensagem}
    headers = {"Authorization": f"Bearer {CHATPRO_TOKEN}",
               "Content-Type": "application/json"}
    return requests.post(CHATPRO_ENDPOINT, json=payload, headers=headers)

# ──────────────────── ENDPOINT WEBHOOK ──────────────────── #

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.json
        if payload.get("eventType") != "FORM_RESPONSE":
            return jsonify({"erro": "Evento ignorado"}), 200

        fields = payload["data"]["fields"]

        # Dados básicos
        nome      = extrair_por_label(fields, "Seu nome completo")
        whatsapp  = extrair_por_label(fields, "Whatsapp")
        cpf       = str(extrair_por_label(fields, "CPF"))
        if not (nome and whatsapp and cpf):
            return jsonify({"erro": "Nome, WhatsApp ou CPF ausentes"}), 400

        # Cursos selecionados → IDs de planos
        cursos_nomes = coletar_cursos(fields)
        planos_ids   = ids_planos_de(cursos_nomes)
        if not planos_ids:
            return jsonify({"erro": "Nenhum curso mapeado"}), 400

        # CPF será o usuário / login
        cadastro = {
            "nome": nome,
            "usuario": cpf,
            "senha": "123456",
            "cpf": cpf,
            "whatsapp": whatsapp,
            "planos": planos_ids,
            "unidade_id": UNIDADE_ID
        }

        # Chamada para sua API de cadastro/matrícula
        headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
        resp_api = requests.post(API_URL, json=cadastro, headers=headers)

        if resp_api.status_code not in (200, 201):
            return jsonify({"erro": "Falha no cadastro", "detalhes": resp_api.text}), 500

        # ░▒▓ ENVIAR WHATSAPP ▓▒░
        num_digits = "".join(filter(str.isdigit, whatsapp))[-11:]  # ddd+numero
        num_55     = f"55{num_digits}"

        data_pagto = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
        lista_cursos = "\n".join(f"• {n}" for n in cursos_nomes)

        msg = (
            f"👋 *Seja bem-vindo(a), {nome}!* \n\n"
            f"🔑 *Acesso*\n"
            f"Login: *{cpf}*\n"
            f"Senha: *123456*\n\n"
            f"📚 *Cursos adquiridos:*\n{lista_cursos}\n\n"
            f"💰 *Data de pagamento:* {data_pagto}\n\n"
            f"🧑‍🏫 *Grupo da sala de aula:*\n"
            f"https://chat.whatsapp.com/Gzn00RNW15ABBfmTc6FEnP"
        )

        enviar_whatsapp(num_55, msg)

        return jsonify({"status": "Aluno cadastrado, matriculado e notificado."}), 200

    except Exception as e:
        return jsonify({"erro": "Exceção interna", "detalhes": str(e)}), 500

# ──────────────────── MAIN ──────────────────── #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
