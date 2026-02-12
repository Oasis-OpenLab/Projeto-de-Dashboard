import os
from datetime import datetime

# 1. CONFIGURAÇÕES MySQL
HOST = "localhost"
USUARIO = "root"
SENHA = " "  
NOME = "Oasis"

# 2. CONFIGURAÇÕES GERAIS
CONSULTA_USUARIO = "Regulamentação inteligência artificial e algoritmos"
DATA_INICIO_COLETA = datetime(2023, 1, 1)
MODELO_NOME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Pesos do filtro
PESO_SEMANTICO = 0.5
PESO_KEYWORD = 0.5    
FILTRO_THRESHOLD = 0.45

