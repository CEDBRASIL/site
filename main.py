from flask import Flask, request
import requests, json, base64
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# === Configurações ============================================================
API_BASE_URL = "https://meuappdecursos.com.br/ws/v2"
API_KEY      = "e6fc583511b1b88c34bd2a2610248a8c"   # coloque em variável de ambiente em produção
UNIDADE_ID   = 4158

unidade_token = None   # será renovado periodicamente

# === Utilidades ==============================================================

def enviar_log_discord(msg: str) -> None:
    webhook_url = ("https://discord.com/api/webhooks/"
                   "1375958173743186081/YCUI_zi3klgvyo9ihgNKli_IaxYeRLV-ScZN9_Q8zxKK4gWAdshKSewHPvfcZ1J5G_Sj")
    try:
        r = requests.post(webhook_url, json={"content": msg}, timeout=10)
        if r.status_code != 204:
            print(f"[Discord] {r.status_code} {r.text}")
    except Exception as exc:
        print(f"[Discord] erro: {exc}")

# === Autenticação ============================================================

def obter_token_unidade() -> None:
    """Renova o token da unidade e mantém em cache global."""
    global unidade_token
    url = f"{API_BASE_URL}/unidades/token/{UNIDADE_ID}"

    # Envia Authorization: Basic <base64(username:password)>
    try:
        resp = requests.get(url,
                            auth=HTTPBasicAuth(API_KEY, ""),   # senha vazia
                            headers={"Accept": "application/json"},
                            timeout=10)
        data = resp.json()
        enviar_log_discord(f"📡 Token-req {resp.status_code} {data}")

        if resp.status_code == 200 and data.get("status") == "true":
            unidade_token = data["data"]["token"]
        else:
            raise RuntimeError(f"Token não obtido: {data}")
    except Exception as exc:
        enviar_log_discord(f"❌ Exceção ao obter token: {exc}")
        raise

# === Endpoints internos ======================================================

@app.route("/secure", methods=["GET", "HEAD"])
def secure_check():
    try:
        obter_token_unidade()
        msg = "🔐 Token atualizado com sucesso"
        enviar_log_discord(msg)
        return msg, 200
    except Exception as exc:
        msg = f"Erro ao atualizar token: {exc}"
        enviar_log_discord(msg)
        return msg, 500

# === Operações de Alunos & Matrículas ========================================

def cadastrar_aluno(nome: str, whatsapp: str, cpf: str) -> int:
    url = f"{API_BASE_URL}/alunos"

    # Teste 1: usar Basic Auth como no /token
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {base64.b64encode(f'{API_KEY}:'.encode()).decode()}"
    }

    payload = {
        "nome": nome,
        "whatsapp": whatsapp,
        "cpf": cpf,
        "unidade_id": UNIDADE_ID
    }

    r = requests.post(url, headers=headers, json=payload, timeout=10)
    data = r.json()

    enviar_log_discord(f"📡 Cadastrar aluno {payload} -> {r.status_code} {data}")

    if r.status_code == 201:
        return data["data"]["id"]
    raise RuntimeError(f"Erro ao cadastrar aluno: {data}")


# === Mapas de cursos & processamento Tally ===================================

def carregar_mapeamento_cursos() -> dict[str, list[int]]:
    return {
        "Excel PRO": [161, 197, 201],
        "Design Gráfico": [254, 751, 169],
        "Analise & Desenvolvimento de Sistemas": [590, 176, 239, 203],
        "Administração": [129, 198, 156, 154],
        "Inglês Fluente": [263, 280, 281],
        "Inglês Kids": [266],
        "Informática Essencial": [130, 599, 161, 160, 162],
        "Operador de Micro": [130, 599, 161, 160, 162],
        "Especialista em Marketing & Vendas": [123, 199, 202, 264, 441,
                                              780, 828, 829, 236, 734]
    }

def processar_evento_tally(evento: dict) -> None:
    campos = evento["data"]["fields"]
    nome, whatsapp, cpf, cursos_desejados = (campos[0]["value"],
                                             campos[1]["value"],
                                             campos[2]["value"],
                                             campos[3]["value"])

    mapping = carregar_mapeamento_cursos()
    curso_ids = [id_
                 for curso in cursos_desejados
                 for nome_curso, ids in mapping.items()
                 if curso in nome_curso
                 for id_ in ids]

    aluno_id = cadastrar_aluno(nome, whatsapp, cpf)
    matricular_aluno(aluno_id, curso_ids)

# === App Runner ==============================================================

if __name__ == "__main__":
    obter_token_unidade()                         # renova token ao subir
    with open("Eventlog.json", encoding="utf-8") as fh:
        processar_evento_tally(json.load(fh))
    app.run(host="0.0.0.0", port=5000)
