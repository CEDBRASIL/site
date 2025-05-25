from fastapi import FastAPI, Request, HTTPException
import requests
import re

app = FastAPI()

# Mapeamento do produto para lista de IDs dos cursos
MAPEAMENTO_CURSOS = {
    "CED - CENTRO DE ENSINO DIGITAL": [
        1234, 5678, 91011  # Substitua pelos IDs reais dos cursos
    ]
}

@app.post("/webhook")
async def receber_webhook(request: Request):
    dados = await request.json()
    print("Webhook recebido:", dados)

    # Valida token do webhook
    token_webhook = request.headers.get("x-webhook-token")
    if token_webhook != "aiz9u0wgb00":
        raise HTTPException(status_code=401, detail="Token inválido")

    # Processa somente evento de pedido aprovado
    if dados.get("webhook_event_type") != "order_approved":
        return {"status": "ignorado", "mensagem": "Evento não é de aprovação"}

    nome_curso = dados.get("Product", {}).get("product_name", "")
    cliente = dados.get("Customer", {})
    nome = cliente.get("name", "")
    email = cliente.get("email", "")
    telefone = cliente.get("phone_number", "")
    cpf = cliente.get("cpf", "")

    # Limpa o CPF para só números
    cpf_limpo = re.sub(r"\D", "", cpf)
    usuario = cpf_limpo

    if nome_curso not in MAPEAMENTO_CURSOS:
        return {"status": "erro", "mensagem": "Curso não mapeado"}

    lista_cursos = MAPEAMENTO_CURSOS[nome_curso]

    payload = {
        "nome": nome,
        "email": email,
        "usuario": usuario,
        "senha": "12345678",
        "unidade": 4158,
        "telefone": telefone,
        "cpf": cpf_limpo,
        "cursos": lista_cursos
    }

    headers = {
        "accept": "application/json",
        "Authorization": "Basic e6fc583511b1b88c34bd2a2610248a8c",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://ead.plataformavlib.com.br/api/usuarios",
        json=payload,
        headers=headers
    )

    if response.status_code == 200:
        mensagem = (
            f"Olá {nome}, sua matrícula foi realizada com sucesso na plataforma CED!\n"
            f"Acesse: https://ead.plataformavlib.com.br\n"
            f"Usuário (CPF): {usuario}\n"
            f"Senha: 12345678"
        )
        requests.post(
            "https://v5.chatpro.com.br/chatpro-xcpvtq83bk/messages/send-text",
            json={"number": telefone, "message": mensagem},
            headers={"Authorization": "Bearer 566fa7beb56fc88e10a0176bbd27f639"}
        )
        return {"status": "sucesso", "mensagem": "Aluno matriculado e WhatsApp enviado"}
    else:
        return {
            "status": "erro",
            "mensagem": "Falha ao cadastrar aluno",
            "detalhes": response.text
        }
