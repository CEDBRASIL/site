from fastapi import FastAPI, Request, HTTPException
import httpx
import asyncio

app = FastAPI()

API_BASE = "https://meuappdecursos.com.br/ws/v2"
CHATPRO_INSTANCIA = "chatpro-2a6ajg7xtk"
CHATPRO_TOKEN = "e10f158f102cd06bb3e8f135e159dd0f"
CHATPRO_ENDPOINT = f"https://v5.chatpro.com.br/{CHATPRO_INSTANCIA}/send-message"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj"

COURSE_MAP = {
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

async def send_discord_log(message: str):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(DISCORD_WEBHOOK_URL, json={"content": message})
        except Exception as e:
            print(f"Erro ao enviar log para Discord: {e}")

def get_course_text_by_id(id_, options):
    for option in options:
        if option["id"] == id_:
            return option["text"]
    return None

async def criar_aluno(nome: str, whatsapp: str, cpf: str):
    payload = {
        "nome_completo": nome,
        "whatsapp": whatsapp,
        "cpf": cpf
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_BASE}/alunos", json=payload)
        if res.status_code != 200:
            raise Exception(f"Erro ao criar aluno: {res.text}")
        data = res.json()
        if not data.get("status") == "true":
            raise Exception(f"Falha na criação do aluno: {data}")
        return data["data"]["id"]

async def matricular_aluno(id_aluno: int, id_curso: int):
    payload = {"curso_id": id_curso}  # Ajuste se a API pedir outro formato
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{API_BASE}/alunos/matricula/{id_aluno}", json=payload)
        if res.status_code != 200:
            raise Exception(f"Erro ao matricular aluno: {res.text}")
        data = res.json()
        if not data.get("status") == "true":
            raise Exception(f"Falha na matrícula: {data}")
        return data

async def enviar_whatsapp(whatsapp: str, mensagem: str):
    numero = ''.join(filter(str.isdigit, whatsapp))
    payload = {
        "phone": numero,
        "message": mensagem
    }
    headers = {"Authorization": f"Bearer {CHATPRO_TOKEN}"}
    async with httpx.AsyncClient() as client:
        res = await client.post(CHATPRO_ENDPOINT, json=payload, headers=headers)
        if res.status_code != 200:
            raise Exception(f"Erro ao enviar WhatsApp: {res.text}")
        return res.json()

@app.post("/webhook/tally")
async def webhook_tally(request: Request):
    try:
        body = await request.json()
        data = body.get("data", {})
        fields = data.get("fields", [])

        nome = next((f["value"] for f in fields if f["label"] == "Seu nome completo"), None)
        whatsapp = next((f["value"] for f in fields if f["label"] == "Whatsapp"), None)
        cpf = next((f["value"] for f in fields if f["label"] == "CPF"), None)

        curso_desejado_field = next((f for f in fields if f["label"] == "Curso Desejado"), None)
        cursos_extras_field = next((f for f in fields if f["label"] == "Curso extra (Adicional de R$5.00 na assinatura)"), None)

        if not nome or not whatsapp:
            await send_discord_log("Dados incompletos: nome ou whatsapp não informado.")
            raise HTTPException(status_code=400, detail="Dados incompletos")

        curso_desejado_ids = curso_desejado_field.get("value", []) if curso_desejado_field else []
        cursos_extras_ids = cursos_extras_field.get("value", []) if cursos_extras_field else []

        curso_desejado_nomes = [get_course_text_by_id(id_, curso_desejado_field["options"]) for id_ in curso_desejado_ids if curso_desejado_field]
        cursos_extras_nomes = [get_course_text_by_id(id_, cursos_extras_field["options"]) for id_ in cursos_extras_ids if cursos_extras_field]

        todos_cursos_nomes = [c for c in curso_desejado_nomes + cursos_extras_nomes if c]

        if len(todos_cursos_nomes) == 0:
            await send_discord_log(f"Nenhum curso selecionado para o aluno {nome}")
            raise HTTPException(status_code=400, detail="Nenhum curso selecionado")

        todos_cursos_ids = []
        for curso in todos_cursos_nomes:
            ids = COURSE_MAP.get(curso)
            if ids:
                todos_cursos_ids.extend(ids)

        if len(todos_cursos_ids) == 0:
            await send_discord_log(f"Cursos selecionados não possuem IDs válidos para o aluno {nome}")
            raise HTTPException(status_code=400, detail="Cursos inválidos")

        id_aluno = await criar_aluno(nome, whatsapp, str(cpf))
        await send_discord_log(f"Aluno criado: {nome} - ID: {id_aluno}")

        for curso_id in todos_cursos_ids:
            await matricular_aluno(id_aluno, curso_id)
            await send_discord_log(f"Aluno {nome} matriculado no curso ID: {curso_id}")

        mensagem = f"Olá {nome}, sua matrícula foi realizada com sucesso em nossos cursos. Seja bem-vindo(a)!"
        await enviar_whatsapp(whatsapp, mensagem)
        await send_discord_log(f"Mensagem WhatsApp enviada para {whatsapp}")

        return {"status": "ok", "message": "Matrícula concluída"}

    except Exception as e:
        await send_discord_log(f"Erro no webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno")
