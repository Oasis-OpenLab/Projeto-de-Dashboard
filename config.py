import os
from datetime import datetime

# --- MAPEAMENTO INTELIGENTE DE PASTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(BASE_DIR, "banco_de_dados_local")
PASTA_CSV = os.path.join(BASE_DIR, "projetos_em_csv")

# 1. CONFIGURAÇÕES MySQL
HOST = "localhost"
USUARIO = "root"
SENHA = ""  # Coloque sua senha aqui
NOME = "Oasis"

# 2. CONFIGURAÇÕES GERAIS DA IA
dispositivo = "cpu"    #escolha entre cpu e gpu, para alternar entre processador e placa gráfica
CONSULTA_USUARIO = "Regulamentação inteligência artificial"
DATA_INICIO_COLETA = datetime(2015, 1, 1) 
MODELO_NOME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# --- NOVO: INTERRUPTOR DA API ---
# True = Conecta na Câmara e baixa projetos novos. False = Usa só o que já tem salvo (Muito mais rápido!)
ATUALIZAR_BASE_API = False 

# 3. PESOS E NOTAS DE CORTE DO FILTRO HÍBRIDO
PESO_SEMANTICO = 0.8
PESO_KEYWORD = 0.2   
FILTRO_THRESHOLD = 0.40
THRESHOLD_SEMANTICO_MINIMO = 0.30