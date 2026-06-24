"""
Módulo de Geração de Embeddings Semânticos para Textos Legislativos.

Responsável por:
- Carregar o modelo de Linguagem (LLM) Sentence-Transformers localmente.
- Ler os arquivos JSON contendo as ementas dos projetos.
- Converter o texto limpo das ementas em vetores matemáticos (Tensores PyTorch).
- Salvar os vetores em formato binário (.pkl) para uso como cache offline,
  garantindo buscas em tempo real nas próximas execuções.
"""
import os
import json
import pickle
import glob
import torch
from sentence_transformers import SentenceTransformer
import config
from utils_legislativo import limpar_ementa_para_vetorizacao

# ==========================================================
# 1. Carregamento do Modelo
# ==========================================================
def get_model():
    """
    Inicializa e retorna o modelo de Inteligência Artificial para embeddings.
    
    O modelo específico e a alocação de hardware (CPU, GPU CUDA, ou Apple MPS)
    são definidos dinamicamente no arquivo config.py.

    Returns:
        SentenceTransformer: O modelo de LLM carregado na memória.
    """
    return SentenceTransformer(
        config.MODELO_NOME,
        device=config.dispositivo
    )

# ==========================================================
# 2. Função de Processamento Principal (Híbrida)
# ==========================================================
def gerar_embeddings_para_legislatura(model, arquivo_json, pbar=None, status_text=None):
    """
    Processa as proposições de uma legislatura e gera seu respectivo arquivo de cache (.pkl).

    Realiza o processamento em lotes (batches) para evitar estouro de memória RAM/VRAM
    e permite a integração com componentes de UI (como barras de progresso no Streamlit).

    Args:
        model (SentenceTransformer): O modelo de IA carregado.
        arquivo_json (str): Caminho absoluto para o arquivo JSON contendo os dados brutos.
        pbar (streamlit.empty, opcional): Objeto de barra de progresso do Streamlit.
        status_text (streamlit.empty, opcional): Objeto de texto de status do Streamlit.

    Returns:
        int: O número total de proposições vetorizadas.
    """
    nome_base = os.path.basename(arquivo_json)
    # Extrai o sufixo (ex: leg56) para nomear o cache
    sufixo_leg = nome_base.replace("camara_db_", "").replace(".json", "")

    msg = f"Processando {sufixo_leg}..."
    
    # Feedback visual (Streamlit)
    if status_text:
        status_text.write(f"📂 {msg}")
    
    # Feedback no console (Terminal)
    print(f"\n{msg}", flush=True)

    # Carregamento dos dados originais
    with open(arquivo_json, 'r', encoding='utf-8') as f: 
        dados = json.load(f)

    # Limpeza das ementas antes da vetorização
    ementas_limpas = [
        limpar_ementa_para_vetorizacao(p.get('ementa', ''))
        for p in dados
    ]

    total_propostas = len(ementas_limpas)
    batch_size = 64
    all_embeddings = []

    # Loop por lotes (batches) para permitir atualização da barra de progresso
    for i in range(0, total_propostas, batch_size):
        batch = ementas_limpas[i : i + batch_size]
        
        # Gera os embeddings do lote atual
        # show_progress_bar=False para não conflitar com a UI do Streamlit
        embedding_lote = model.encode(
            batch, 
            convert_to_tensor=True, 
            show_progress_bar=False 
        )
        
        # Movemos para CPU para economizar VRAM/RAM e garantir portabilidade do Pickle
        all_embeddings.append(embedding_lote.cpu())

        # Se o objeto da barra de progresso foi passado, atualizamos a interface
        if pbar:
            progresso = min((i + batch_size) / total_propostas, 1.0)
            pbar.progress(progresso, text=f"Vetorizando {sufixo_leg}: {min(i + batch_size, total_propostas)} de {total_propostas}")

    # Concatena todos os lotes em um único tensor
    embeddings_final = torch.cat(all_embeddings, dim=0)

    # Define o caminho de saída conforme config.py
    caminho_saida = os.path.join(
        config.PASTA_DADOS,
        f"cache_ementas_{sufixo_leg}.pkl"
    )

    # Salva o arquivo de cache
    with open(caminho_saida, 'wb') as f:
        pickle.dump(embeddings_final, f)

    print(f"✔ Embeddings salvos com sucesso em: {caminho_saida}", flush = True)
    return total_propostas

# ==========================================================
# FUNÇÃO DE COMPATIBILIDADE (Para evitar erro no Filtrador)
# ==========================================================
def get_or_create_embeddings(dados, sufixo_leg, model):
    """
    Gerenciador inteligente de Cache de Embeddings.

    Verifica se os vetores da legislatura solicitada já existem no disco.
    Se sim, carrega e move para a memória/GPU. Se não, dispara a geração,
    salva e depois carrega.

    Args:
        dados (list): Lista de dicionários com os projetos de lei.
        sufixo_leg (str): Identificador da legislatura (ex: 'leg57').
        model (SentenceTransformer): O modelo de IA em uso.

    Returns:
        torch.Tensor: Tensor multidimensional com os vetores de todas as ementas daquele lote.
    """
    arquivo_cache = os.path.join(config.PASTA_DADOS, f"cache_ementas_{sufixo_leg}.pkl")
    caminho_json = os.path.join(config.PASTA_DADOS, f"camara_db_{sufixo_leg}.json")

    # 1. Se o arquivo já existe, abre e retorna o tensor
    if os.path.exists(arquivo_cache):
        with open(arquivo_cache, 'rb') as f:
            embeddings = pickle.load(f)
            # Garante que seja float logo aqui
            return embeddings.float().to(config.dispositivo) if hasattr(embeddings, 'float') else embeddings.to(config.dispositivo)

    # 2. Se não existe, gera, salva e DEPOIS retorna o tensor
    # (Note que aqui chamamos a função de geração)
    gerar_embeddings_para_legislatura(model, caminho_json)
    
    # Após gerar, precisamos ler o que foi salvo para retornar o objeto
    with open(arquivo_cache, 'rb') as f:
        embeddings = pickle.load(f)
        return embeddings.float().to(config.dispositivo)

# ==========================================================
# 3. Lógica Main (Execução via Terminal)
# ==========================================================
def main():
    """
    Ponto de entrada para execução em modo de terminal (Offline/Batch Mode).
    Varre a pasta de dados e processa todos os arquivos JSON encontrados.
    """
    print("=== INICIANDO PROCESSAMENTO DE EMBEDDINGS (MODO OFFLINE) ===", flush = True)
    
    print("Carregando modelo de IA...", flush=True)
    model = get_model()

    # Busca todos os arquivos JSON que seguem o padrão definido
    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_json = glob.glob(padrao_busca)

    if not arquivos_json:
        print(f"Erro: Nenhum arquivo JSON encontrado em {config.PASTA_DADOS}", flush = True)
        return

    print(f"Encontrados {len(arquivos_json)} arquivo(s). Iniciando loop...", flush = True)

    for arquivo_json in arquivos_json:
        # Chama a função principal sem os parâmetros de UI (pbar=None, status_text=None)
        gerar_embeddings_para_legislatura(model, arquivo_json)

    print("\n✅ Todos os arquivos foram processados e indexados!", flush = True)

if __name__ == "__main__":
    main()