#!/bin/bash

# Atualizando e instalando dependências
echo "Instalando dependências..."
pip install -r requirements.txt

# Rodando o servidor Flask
echo "Iniciando servidor Flask..."
python main.py
