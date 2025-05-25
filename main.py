from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Mapeamento dos cursos para os IDs de planos
curso_plano_map = {
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

# Configurações da API (exemplo)
API_URL = "https://meuappdecursos.com.br/ws/v2/"
API_TOKEN = "e6fc583511b1b88c34bd2a2610248a8c"
UNIDADE_ID = 4158

def extrair_valores_campo(fields, label):
    """Extrai valor do campo no payload do Tally pelo label"""
    for field in fields:
        if field.get("label") == label:
            return field.get("value")
    return None

def obter_planos(cursos_ids):
    """Dado uma lista de cursos (ids do Tally), retorna os planos correspondentes"""
    planos = []
    for curso_id in cursos_ids:
        # Encontrar o texto do curso pelo id
        for field in payload['data']['fields']:
            if field['key'] == "question_pyEOz8" or field['key'] == "question_ZE7655":
                for option in field.get("options", []):
                    if option['id'] == curso_id:
                        curso_nome = option['text']
                        planos.extend(curso_plano_map.get(curso_nome, []))
    return list(set(planos))  # Remove duplicados

@app.route("/webhook", methods=["POST"])
def webhook():
    global payload
    payload = request.json

    # Extrair dados do formulário
    fields = payload.get("data", {}).get("fields", [])

    nome = extrair_valores_campo(fields, "Seu nome completo")
    whatsapp = extrair_valores_campo(fields, "Whatsapp")
    cpf = extrair_valores_campo(fields, "CPF")

    # Cursos desejados e cursos extras
    cursos_desejados = extrair_valores_campo(fields, "Curso Desejado") or []
    cursos_extras = extrair_valores_campo(fields, "Curso extra (Adicional de R$5.00 na assinatura)") or []

    # Obter planos a partir dos cursos
    planos = obter_planos(cursos_desejados) + obter_planos(cursos_extras)
    planos = list(set(planos))  # remover duplicados

    if not planos:
        return jsonify({"error": "Nenhum plano válido encontrado para os cursos selecionados."}), 400

    # Montar payload para cadastro
    cadastro_payload = {
        "nome": nome,
        "cpf": str(cpf),
        "whatsapp": whatsapp,
        "planos": planos,
        "unidade_id": UNIDADE_ID
    }

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Chamar API para cadastro do aluno
    resposta = requests.post(API_URL, json=cadastro_payload, headers=headers)

    if resposta.status_code == 201:
        return jsonify({"status": "Aluno cadastrado e matriculado com sucesso."})
    else:
        return jsonify({"error": "Falha ao cadastrar aluno.", "detalhes": resposta.text}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
