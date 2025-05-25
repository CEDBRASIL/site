from flask import Flask, request, jsonify import requests from requests.auth import HTTPBasicAuth import datetime import os import json

app = Flask(name)

CONFIGURAÇÕES FIXAS

OURO_BASE_URL = "https://meuappdecursos.com.br/ws/v2" BASIC_AUTH = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6" SUPORTE_WHATSAPP = "61981969018" DATA_FIM = (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d")

CHATPRO_TOKEN = "61de03bbdfbfca09d33ca6c2ec9c73f9" CHATPRO_INSTANCIA = "chatpro-h9bsk4dljx" CHATPRO_URL = f"https://v5.chatpro.com.br/{CHATPRO_INSTANCIA}/api/v1/send_message"

CALLMEBOT_APIKEY = "2712587" CALLMEBOT_PHONE = "556186660241"

MAPEAMENTO_CURSOS = { "Excel PRO": [161, 197, 201], "Design Gráfico": [254, 751, 169], "Analista de Tecnologia da Informação (TI)": [590, 176, 239, 203], "Administração": [129, 198, 156, 154], "Inglês Fluente": [263, 280, 281], "Marketing Digital": [734, 236, 441, 199, 780], "teste": [161, 201], "Example plan": [161, 201], "Operador de micro/Maria": [130, 599, 163, 160, 161, 162, 222], "Inglês Kids": [266], "Informática Essencial": [130, 599, 161, 160, 162], "Operador de Micro": [130, 599, 161, 160, 162], "Especialista em Marketing e Vendas 360º": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734], "teste": [123, 199, 202, 264, 441, 780, 828, 829, 236, 734] }

API_URL = "https://meuappdecursos.com.br/ws/v2/unidades/token/" ID_UNIDADE = 4158 KEY = "e6fc583511b1b88c34bd2a2610248a8c"

TOKEN_UNIDADE = None

def enviar_log_discord(mensagem): try: url = "https://discord.com/api/webhooks/1374816975628402708/PCaAOawTso2vuYkKQYF39MIzyswaj1Se1RmA8fbKUqS3zBn2i6_WmSSS-f4zwNFcKgP2" payload = {"content": mensagem} headers = {"Content-Type": "application/json"} resp = requests.post(url, data=json.dumps(payload), headers=headers) if resp.status_code == 204: print("✅ Log enviado ao Discord com sucesso.") else: print("❌ Falha ao enviar log para Discord:", resp.text) except Exception as e: print("❌ Erro ao enviar log para Discord:", str(e))

def enviar_log_whatsapp(mensagem): try: msg_formatada = requests.utils.quote(mensagem) url = f"https://api.callmebot.com/whatsapp.php?phone={CALLMEBOT_PHONE}&text={msg_formatada}&apikey={CALLMEBOT_APIKEY}" resp = requests.get(url) if resp.status_code == 200: print("✅ Log enviado ao WhatsApp com sucesso.") else: print("❌ Falha ao enviar log para WhatsApp:", resp.text) except Exception as e: print("❌ Erro ao enviar log para WhatsApp:", str(e)) finally: enviar_log_discord(mensagem)

def obter_token_unidade(): global TOKEN_UNIDADE try: resposta = requests.get(API_URL + f"{ID_UNIDADE}", auth=HTTPBasicAuth(KEY, "")) dados = resposta.json() if dados.get("status") == "true": TOKEN_UNIDADE = dados.get("data")["token"] mensagem = "🔁 Token atualizado com sucesso!" print(mensagem) enviar_log_discord(mensagem) return TOKEN_UNIDADE mensagem = f"❌ Erro ao obter token: {dados}" print(mensagem) enviar_log_whatsapp(mensagem) except Exception as e: mensagem = f"❌ Exceção ao obter token: {str(e)}" print(mensagem) enviar_log_whatsapp(mensagem) return None

Inicializa o token ao iniciar o app

obter_token_unidade()

@app.before_request def log_request_info(): mensagem = ( f"\n📥 Requisição recebida:\n" f"🔗 URL completa: {request.url}\n" f"📍 Método: {request.method}\n" f"📦 Cabeçalhos: {dict(request.headers)}" ) print(mensagem) enviar_log_discord(mensagem)

@app.route('/secure', methods=['GET', 'HEAD']) def secure_check(): obter_token_unidade() return "🔐 Token atualizado com sucesso via /secure", 200

def buscar_aluno_por_cpf(cpf): try: print(f"🔍 Buscando aluno com CPF: {cpf}") resp = requests.get( f"{OURO_BASE_URL}/alunos", headers={"Authorization": f"Basic {BASIC_AUTH}"}, params={"cpf": cpf} )

if not resp.ok:
        print(f"❌ Falha ao buscar aluno: {resp.text}")
        return None

    alunos = resp.json().get("data", [])
    if not alunos:
        print("❌ Nenhum aluno encontrado com o CPF fornecido.")
        return None

    aluno_id = alunos[0].get("id")
    print(f"✅ Aluno encontrado. ID: {aluno_id}")
    return aluno_id

except Exception as e:
    print(f"❌ Erro ao buscar aluno: {str(e)}")
    return None

@app.route('/webhook', methods=['POST']) def webhook(): try: print("\n🔔 Webhook recebido com sucesso") payload = request.json evento = payload.get("webhook_event_type")

if evento == "order_refunded":
        customer = payload.get("Customer", {})
        cpf = customer.get("CPF", "").replace(".", "").replace("-", "")

        if not cpf:
            erro_msg = "❌ CPF do aluno não encontrado no payload de reembolso."
            print(erro_msg)
            enviar_log_whatsapp(erro_msg)
            enviar_log_discord(erro_msg)
            return jsonify({"error": "CPF do aluno não encontrado."}), 400

        aluno_id = buscar_aluno_por_cpf(cpf)
        if not aluno_id:
            erro_msg = "❌ ID do aluno não encontrado para o CPF fornecido."
            print(erro_msg)
            enviar_log_whatsapp(erro_msg)
            enviar_log_discord(erro_msg)
            return jsonify({"error": "ID do aluno não encontrado."}), 400

        print(f"🗑️ Excluindo conta do aluno com ID: {aluno_id}")
        resp_exclusao = requests.delete(
            f"{OURO_BASE_URL}/alunos/{aluno_id}",
            headers={"Authorization": f"Basic {BASIC_AUTH}"}
        )

        if not resp_exclusao.ok:
            erro_msg = (
                f"❌ ERRO AO EXCLUIR ALUNO\n"
                f"Aluno ID: {aluno_id}\n"
                f"🔧 Detalhes: {resp_exclusao.text}"
            )
            print(erro_msg)
            enviar_log_whatsapp(erro_msg)
            enviar_log_discord(erro_msg)
            return jsonify({"error": "Falha ao excluir aluno", "detalhes": resp_exclusao.text}), 500

        msg_exclusao = f"✅ Conta

