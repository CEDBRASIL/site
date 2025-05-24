from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# Configurações fixas
TOKEN_UNIDADE = "SEU_TOKEN_UNIDADE"
BASIC_AUTH = "Basic SUA_CHAVE_AUTH"
OURO_BASE_URL = "https://plataforma.cedbrasil.com.br/api"

MAPEAMENTO_CURSOS = {
    "Informática Essencial": [123],
    "Excel PRO": [124],
    "Desigh Gráfico": [125],
    "Analise & Desenvolvimento de Sistemas": [126],
    "Inglês Fluente": [127],
    "Administração": [128],
    "Especialista em Marketing & Vendas": [129],
}

@app.route("/webhook", methods=["POST"])
def webhook_herospark():
    payload = request.get_json(force=True)
    print("🔔 Payload recebido:", json.dumps(payload, indent=2))

    if payload.get("eventType") != "FORM_RESPONSE":
        return jsonify({"message": "Evento ignorado"}), 200

    fields = payload.get("data", {}).get("fields", [])
    nome = cpf = celular = curso_desejado = ""
    email = "sememail@dominio.com"

    for field in fields:
        label = field.get("label", "").strip().lower()
        valor = field.get("value")

        if "nome completo" in label:
            nome = valor
        elif "cpf" in label:
            cpf = str(valor).zfill(11)
        elif "whatsapp" in label or "celular" in label:
            celular = valor
        elif "curso desejado" in label:
            # Pode conter lista
            curso_ids = field.get("value", [])
            opcoes = field.get("options", [])
            curso_desejado = ""
            for opcao in opcoes:
                if opcao["id"] in curso_ids:
                    curso_desejado = opcao["text"]
                    break

    print(f"📋 Dados extraídos: Nome={nome}, CPF={cpf}, Celular={celular}, Curso={curso_desejado}")

    if not cpf:
        msg = "❌ CPF não encontrado no payload do formulário."
        print(msg)
        return jsonify({"error": msg}), 400

    cursos_ids = MAPEAMENTO_CURSOS.get(curso_desejado)
    if not cursos_ids:
        msg = f"❌ Curso '{curso_desejado}' não mapeado."
        print(msg)
        return jsonify({"error": msg}), 400

    dados_aluno = {
        "token": TOKEN_UNIDADE,
        "nome": nome,
        "data_nascimento": "2000-01-01",
        "email": email,
        "fone": celular,
        "senha": "123456",
        "celular": celular,
        "doc_cpf": cpf,
        "doc_rg": "00000000000",
        "pais": "Brasil",
        "uf": "DF",
        "cidade": "Brasília",
        "endereco": "Endereço padrão",
        "complemento": "",
        "bairro": "Bairro padrão",
        "cep": "00000000"
    }

    print("📨 Enviando dados do aluno para a API de cadastro...")
    resp_cadastro = requests.post(
        f"{OURO_BASE_URL}/alunos",
        data=dados_aluno,
        headers={"Authorization": BASIC_AUTH}
    )

    aluno_response = resp_cadastro.json()
    print("📨 Resposta do cadastro:", aluno_response)

    if not resp_cadastro.ok or aluno_response.get("status") != "true":
        return jsonify({"error": "Falha ao criar aluno", "detalhes": aluno_response}), 500

    aluno_id = aluno_response.get("data", {}).get("id")
    if not aluno_id:
        return jsonify({"error": "ID do aluno não encontrado na resposta"}), 500

    dados_matricula = {
        "token": TOKEN_UNIDADE,
        "cursos": ",".join(str(cid) for cid in cursos_ids)
    }

    print(f"📨 Realizando matrícula do aluno {aluno_id}...")
    resp_matricula = requests.post(
        f"{OURO_BASE_URL}/alunos/matricula/{aluno_id}",
        data=dados_matricula,
        headers={"Authorization": BASIC_AUTH}
    )

    matricula_response = resp_matricula.json()
    print("📨 Resposta da matrícula:", matricula_response)

    if not resp_matricula.ok or matricula_response.get("status") != "true":
        return jsonify({"error": "Falha ao matricular aluno", "detalhes": matricula_response}), 500

    return jsonify({"message": f"Aluno {nome} criado e matriculado com sucesso!"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
