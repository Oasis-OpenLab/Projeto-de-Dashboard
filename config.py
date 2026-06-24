"""
Módulo de configurações globais e variáveis de ambiente do Projeto OÁSIS.

Responsável por centralizar:
- Chaves de API (Streamlit Secrets, Cohere).
- Credenciais de conexão com o banco de dados MySQL.
- Caminhos e diretórios do sistema (sharding de dados e CSVs).
- Configurações do modelo de Inteligência Artificial (Sentence Transformers).
- Parâmetros e pesos matemáticos do motor de filtragem híbrida.
"""

import os
from datetime import datetime
import torch  # <-- NOVO IMPORT AQUI
import streamlit as st
import tempfile

import streamlit as st

# --- CONFIGURAÇÕES EXISTENTES (Manter o que já tem) ---
# ... (Seu código de CPU/GPU/Paths) ...

# =====================================================================
# CONFIGURAÇÃO PARA RE-RANKING (COHERE)
# =====================================================================
# Carrega a chave de forma segura dos segredos do Streamlit
COHERE_API_KEY = st.secrets["COHERE_API_KEY"]

# TOP_K_RERANK: Define quantos projetos o Bi-Encoder enviará para o Re-ranking.
TOP_K_RERANK = 50


# --- MAPEAMENTO INTELIGENTE DE PASTAS ---
# Garante que os caminhos funcionem independentemente do sistema operacional (Windows/Linux)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(BASE_DIR, "banco_de_dados_local")
PASTA_CSV = os.path.join(BASE_DIR, "projetos_em_csv")

# 1. CONFIGURAÇÕES MySQL
HOST = st.secrets["HOST"]
USUARIO = st.secrets["USUARIO"]
SENHA = st.secrets["SENHA"]  # Coloque sua senha aqui
NOME = st.secrets["NOME"]
porta = st.secrets["PORTA"]

# 2. CONFIGURAÇÕES GERAIS DA IA E HARDWARE

# Define o ponto de partida temporal para a coleta na API da Câmara
DATA_INICIO_COLETA = datetime(2015, 1, 1) 

# Modelo LLM utilizado para gerar os embeddings das ementas
MODELO_NOME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Detecção automática de aceleração de hardware para otimizar os tensores
if torch.cuda.is_available():
    dispositivo = "cuda"  # Placas de vídeo NVIDIA
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    dispositivo = "mps"   # MacBooks com chip Apple Silicon (M1, M2, M3)
else:
    dispositivo = "cpu"   # Processador padrão de qualquer computador

# Gerenciamento de certificado SSL temporário para conexão segura com o BD
cert_content = st.secrets["CERTIFICADO"]
with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(cert_content.encode())
    certificado = tmp.name

# INTERRUPTOR DA API

# True = Conecta na Câmara e baixa projetos novos. 
# False = Pula a coleta e usa apenas o cache local (ideal para testes rápidos).
ATUALIZAR_BASE_API = False

# 3. PESOS E NOTAS DE CORTE DO FILTRO HÍBRIDO
PESO_SEMANTICO = 0.8
PESO_QUERY_PRINCIPAL = 0.70  # Peso da primeira query, a mais geral
PESO_QUERY_SECUNDARIA = 0.30  # Peso da segunda query, mais refinada
PESO_KEYWORD = 0.2   
FILTRO_THRESHOLD = 0.35
THRESHOLD_SEMANTICO_MINIMO = 0.30
THRESHOLD_SEMANTICO_MINIMO_SECUNDARIA = 0.30