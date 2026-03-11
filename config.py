import os
from datetime import datetime
import torch  # <-- NOVO IMPORT AQUI

# --- MAPEAMENTO INTELIGENTE DE PASTAS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(BASE_DIR, "banco_de_dados_local")
PASTA_CSV = os.path.join(BASE_DIR, "projetos_em_csv")

# 1. CONFIGURAÇÕES MySQL
HOST = "localhost"
USUARIO = "root"
SENHA = "91574602"  # Coloque sua senha aqui
NOME = "Oasis"

# 2. CONFIGURAÇÕES GERAIS DA IA E HARDWARE
CONSULTA_USUARIO = "Regulamentação inteligência artificial"
DATA_INICIO_COLETA = datetime(2015, 1, 1) 
MODELO_NOME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# --- NOVO: DETECÇÃO AUTOMÁTICA DE HARDWARE ---
if torch.cuda.is_available():
    dispositivo = "cuda"  # Placas de vídeo NVIDIA
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    dispositivo = "mps"   # MacBooks com chip Apple Silicon (M1, M2, M3)
else:
    dispositivo = "cpu"   # Processador padrão de qualquer computador

# --- NOVO: INTERRUPTOR DA API ---
# True = Conecta na Câmara e baixa projetos novos. False = Usa só o que já tem salvo (Muito mais rápido!)
ATUALIZAR_BASE_API = False 

# 3. PESOS E NOTAS DE CORTE DO FILTRO HÍBRIDO
PESO_SEMANTICO = 0.8
PESO_KEYWORD = 0.2   
FILTRO_THRESHOLD = 0.40
THRESHOLD_SEMANTICO_MINIMO = 0.30