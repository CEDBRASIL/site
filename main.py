from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import requests
import mercadopago
import threading
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI()

# Permite requisições CORS (opcional, mas recomendado)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Ajuste conforme necessidade de segurança
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variáveis de ambiente
OM_BASE = os.getenv("OM_BASE")  # e.g. https://meuappdecursos.com.br/ws/v2
BASIC_B64 = os.getenv("BASIC_B64")  # Authorization header (Basic base64)
TOKEN_KEY = os.getenv("TOKEN_KEY")  # Token da unidade OM
UNIDADE_ID = os.getenv("UNIDADE_ID")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

CPF_PREFIXO = "20254158"
cpf_lock = threading.Lock()

sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

class CheckoutData(BaseModel):
    nome: str
    whatsapp: str
    cursos: list[int]

def log(mensagem: str):
    print(mensagem)
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": mensagem})
        except Exception as e:
            print(f"Erro ao logar no Discord: {e}")

def total_alunos() -> int:
    url = f"{OM_BASE}/alunos/total/{UNIDADE_ID}"
    r = requests.get(url, headers={"Authorization": f"Basic {BASIC_B64}"})
    if r.ok and r.json().get("status") == "true":
        return int(r.json()["data"]["total"])
    url = f"{OM_BASE}/alunos?unidade_id={UNIDADE_ID}&cpf_like={CPF_PREFIXO}"
    r = requests.get(url, headers={"Authorization": f"Basic {BASIC_B64}"})
    if r.ok and r.json().get("status") == "true":
        return len(r.json()["data"])
    raise RuntimeError("Não foi possível obter o total de alunos.")

def proximo_cpf(incremento: int = 0) -> str:
    with cpf_lock:
        seq = total_alunos() + 1 + incremento
        return CPF_PREFIXO + str(seq).zfill(3)

def cadastrar_aluno(nome: str, whatsapp: str, tentativas: int = 60) -> tuple[str | None, str | None]:
    for i in range(tentativas):
        cpf = proximo_cpf(i)
        cadastro = {
            "token": TOKEN_KEY,
            "nome": nome,
            "whatsapp": whatsapp,
            "data_nascimento": "2000-01-01",
            "fone": whatsapp,
            "celular": whatsapp,
            "doc_cpf": cpf,
            "doc_rg": "000000000",
            "pais": "Brasil",
            "uf": "DF",
            "cidade": "Brasília",
            "endereco": "Não informado",
            "complemento": "",
            "bairro": "Centro",
            "cep": "70000-000"
        }
        r = requests.post(f"{OM_BASE}/alunos", data=cadastro, headers={"Authorization": f"Basic {BASIC_B64}"})
        log(f"[CADASTRO] tentativa {i+1}/{tentativas} | {r.status_code} {r.text}")

        if r.ok and r.json().get("status") == "true":
            return r.json()["data"]["id"], cpf

        info = (r.json() or {}).get("info", "").lower()
        if "já está em uso" not in info:
            break

    log("❌ Falha no cadastro após tentativas")
    return None, None

def matricular_aluno(aluno_id: str, cursos: list[int]) -> bool:
    payload = {
        "token": TOKEN_KEY,
        "cursos": ",".join(map(str, cursos))
    }
    url = f"{OM_BASE}/alunos/matricula/{aluno_id}"
    r = requests.post(url, data=payload, headers={"Authorization": f"Basic {BASIC_B64}"})
    log(f"[MATRÍCULA] {r.status_code} {r.text}")
    return r.ok and r.json().get("status") == "true"

def criar_preferencia_mp(titulo: str, preco: float) -> str | None:
    preference_data = {
        "items": [
            {
                "title": titulo,
                "quantity": 1,
                "unit_price": preco
            }
        ]
    }
    response = sdk.preference().create(preference_data)
    if response["status"] == 201:
        return response["response"]["init_point"]
    return None

@app.post("/checkout")
def processar_checkout(data: CheckoutData):
    aluno_id, usuario = cadastrar_aluno(data.nome, data.whatsapp)
    if not aluno_id:
        raise HTTPException(status_code=400, detail="Falha ao cadastrar aluno")

    if not matricular_aluno(aluno_id, data.cursos):
        raise HTTPException(status_code=400, detail="Falha ao matricular aluno")

    link = criar_preferencia_mp(f"Matrícula - {data.nome}", 59.90)
    if not link:
        raise HTTPException(status_code=500, detail="Falha ao criar link de pagamento")

    log(f"✅ Processo finalizado com sucesso para {data.nome} | Login: {usuario}")
    return {"status": "sucesso", "aluno_id": aluno_id, "usuario": usuario, "mp_link": link}

@app.get("/secure")
def ping():
    return {"status": "ativo"}
