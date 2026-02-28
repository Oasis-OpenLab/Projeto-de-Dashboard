import json
import pickle
import os
import glob
import config
from sentence_transformers import SentenceTransformer
from utils_legislativo import validar_tag

MODELO_NOME = config.MODELO_NOME

def extrair_keywords(dados):
    """
    Percorre todas as proposições de um JSON
    e extrai um conjunto único de keywords/indexações.

    Responsabilidade:
    - limpar
    - validar
    - deduplicar
    - ordenar

    Retorna:
        lista ordenada de keywords únicas.
    """
    # Usamos set para evitar duplicatas automaticamente
    unique_keywords = set()
    for projeto in dados:
        # Algumas bases usam 'keywords'
        # Outras usam 'indexacao'
        texto = projeto.get('keywords') or projeto.get('indexacao')
        if texto:
            # Normaliza separadores
            # Algumas vêm com ";", outras com ","
            for termo in texto.replace(';', ',').split(','):
                # Validação e padronização
                tag = validar_tag(termo)
                # Só adiciona se passou na validação
                if tag: unique_keywords.add(tag)
    return sorted(list(unique_keywords))

if __name__ == "__main__":
    print(f"Carregando modelo de IA...")
    try: model = SentenceTransformer(MODELO_NOME)
    except: exit()

    # Busca os JSONs dentro da nova pasta
    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_db = glob.glob(padrao_busca)

    # Processa cada legislatura separadamente
    for arquivo in arquivos_db:
        nome_base = os.path.basename(arquivo)

        # Extrai o sufixo da legislatura. Ex: camara_db_leg56.json → leg56
        sufixo = nome_base.replace("camara_db_", "").replace(".json", "")

        # Define nome do arquivo de cache das keywords vetorizadas
        arquivo_pkl = os.path.join(config.PASTA_DADOS, f"keywords_embeddings_{sufixo}.pkl")

        # --- NOVO: LÓGICA DE INVALIDAÇÃO DE CACHE (SMART SYNC) ---
        # Pegamos a data e hora exata da última modificação do arquivo JSON bruto
        json_mtime = os.path.getmtime(arquivo)
        precisa_atualizar = True

        # Se o arquivo .pkl (o cache da IA) já existir, comparamos a idade
        if os.path.exists(arquivo_pkl):
            pkl_mtime = os.path.getmtime(arquivo_pkl)
            # Se o Cache for mais "novo" (recente) que o arquivo JSON, significa que não houve mudanças na Câmara
            if pkl_mtime > json_mtime:
                precisa_atualizar = False 

        if precisa_atualizar:
            print(f"\nAtualizando vetores de Keywords para: {nome_base} (Dados Novos Detectados!)")
            # Carrega JSON da legislatura
            with open(arquivo, 'r', encoding='utf-8') as f: dados = json.load(f)
            # Extrai lista única de keywords
            keywords = extrair_keywords(dados)
            if keywords:
                print(f"Vetorizando {len(keywords)} tags...")

                # Gera embeddings vetoriais para cada keyword
                embeddings = model.encode(keywords, batch_size=64, show_progress_bar=True, convert_to_tensor=True)

                # Salva cache em disco
                # Estrutura salva:
                # {
                #   "keywords_texto": [...],
                #   "keywords_vectors": tensor_cpu
                # }
                #
                # Observação:
                # .cpu() é importante se estiver rodando em GPU,
                # porque pickle não salva tensor CUDA corretamente.
                with open(arquivo_pkl, "wb") as f:
                    pickle.dump({"keywords_texto": keywords, "keywords_vectors": embeddings.cpu()}, f)
            print(f"Salvo: {arquivo_pkl}")
        else:
            # Se já existir cache e ele estiver atualizado, evita recalcular
            print(f"Cache de keywords já está sincronizado para {sufixo}. Pulando.")