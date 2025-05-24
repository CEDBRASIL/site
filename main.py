from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import datetime
import json

app = Flask(__name__)

# CONFIGURAÇÕES FIXAS
OURO_BASE_URL = "https://meuappdecursos.com.br/ws/v2"
BASIC_AUTH = "ZTZmYzU4MzUxMWIxYjg4YzM0YmQyYTI2MTAyNDhhOGM6"
SUPORTE_WHATSAPP = "61981969018"
DATA_FIM = (datetime.datetime.now() + datetime.timedelta(days=180)).strftime("%Y-%m-%d")

CHATPRO_TOKEN = "61de03bbdfbfca09d33ca6c2ec9c73f9"
CHATPRO_INSTANCIA = "chatpro-h9bsk4dljx"
CHATPRO_URL = f"https://v5.chatpro.com.br/{CHATPRO_INSTANCIA}/api/v1/send_message"

CALLMEBOT_APIKEY = "2712587"
CALLMEBOT_PHONE = "556186660241"

API_URL = "https://meuappdecursos.com.br/ws/v2/unidades/token/"
ID_UNIDADE = 4158
KEY = "e6fc583511b1b88c34bd2a2610248a8c"

TOKEN_UNIDADE = None

def enviar_log_discord(mensagem):
    try:
        url = "https://discord.com/api/webhooks/1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"
        payload = {"content": mensagem}
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, data=json.dumps(payload), headers=headers)
        if resp.status_code == 204:
            print("✅ Log enviado ao Discord com sucesso.")
        else:
            print("❌ Falha ao enviar log para Discord:", resp.text)
    except Exception as e:
        print("❌ Erro ao enviar log para Discord:", str(e))

def enviar_log_whatsapp(mensagem):
    try:
        msg_formatada = requests.utils.quote(mensagem)
        url = f"https://api.callmebot.com/whatsapp.php?phone={CALLMEBOT_PHONE}&text={msg_formatada}&apikey={CALLMEBOT_APIKEY}"
        resp = requests.get(url)
        if resp.status_code == 200:
            print("✅ Log enviado ao WhatsApp com sucesso.")
        else:
            print("❌ Falha ao enviar log para WhatsApp:", resp.text)
    except Exception as e:
        print("❌ Erro ao enviar log para WhatsApp:", str(e))
    finally:
        enviar_log_discord(mensagem)

def obter_token_unidade():
    global TOKEN_UNIDADE
    try:
        resposta = requests.get(API_URL + f"{ID_UNIDADE}", auth=HTTPBasicAuth(KEY, ""))
        dados = resposta.json()
        if dados.get("status") == "true":
            TOKEN_UNIDADE = dados.get("data")["token"]
            mensagem = "🔁 Token atualizado com sucesso!"
            print(mensagem)
            enviar_log_discord(mensagem)
            return TOKEN_UNIDADE
        mensagem = f"❌ Erro ao obter token: {dados}"
        print(mensagem)
        enviar_log_whatsapp(mensagem)
    except Exception as e:
        mensagem = f"❌ Exceção ao obter token: {str(e)}"
        print(mensagem)
        enviar_log_whatsapp(mensagem)
    return None

# Inicializa o token ao iniciar o app
obter_token_unidade()

@app.before_request
def log_request_info():
    mensagem = (
        f"\n📥 Requisição recebida:\n"
        f"🔗 URL completa: {request.url}\n"
        f"📍 Método: {request.method}\n"
        f"📦 Cabeçalhos: {dict(request.headers)}"
    )
    print(mensagem)
    enviar_log_discord(mensagem)

@app.route('/secure', methods=['GET', 'HEAD'])
def secure_check():
    obter_token_unidade()
    return "🔐 Token atualizado com sucesso via /secure", 200

def buscar_aluno_por_cpf(cpf):
    try:
        print(f"🔍 Buscando aluno com CPF: {cpf}")
        resp = requests.get(
            f"{OURO_BASE_URL}/alunos",
            headers={"Authorization": f"Basic {BASIC_AUTH}"},
            params={"cpf": cpf}
        )

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

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        payload = request.json
        print("Payload recebido:", json.dumps(payload, indent=2))

        # Extrair CPF do payload do tally.so (campo com ref 'cpf')
        cpf = None
        if "answers" in payload:
            for ans in payload["answers"]:
                if ans.get("field", {}).get("ref") == "cpf":
                    cpf = ans.get("text", "").replace(".", "").replace("-", "")
                    break

        if not cpf:
            erro_msg = "❌ CPF não encontrado no payload do formulário."
            print(erro_msg)
            enviar_log_whatsapp(erro_msg)
            enviar_log_discord(erro_msg)
            return jsonify({"error": "CPF não encontrado no payload"}), 400

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

        msg_exclusao = f"✅ Conta do aluno com ID {aluno_id} excluída com sucesso."
        print(msg_exclusao)
        enviar_log_whatsapp(msg_exclusao)
        enviar_log_discord(msg_exclusao)

        return jsonify({"status": "Conta excluída com sucesso"}), 200

    except Exception as e:
        erro_msg = f"❌ Exceção no processamento do webhook: {str(e)}"
        print(erro_msg)
        enviar_log_whatsapp(erro_msg)
        enviar_log_discord(erro_msg)
        return jsonify({"error": "Erro interno"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
