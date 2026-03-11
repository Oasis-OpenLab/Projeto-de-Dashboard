import json
import pickle
import os
import glob
import config
from utils_legislativo import validar_tag
from embeddings import get_model

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
    print("Carregando modelo de IA...")
    # Carrega o modelo de embeddings (ex: SentenceTransformer do HuggingFace)
    model = get_model()

    # Define o padrão de busca para encontrar todos os arquivos JSON da base da Câmara
    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_db = glob.glob(padrao_busca)

    # Itera sobre cada arquivo JSON encontrado na pasta de dados
    for arquivo in arquivos_db:
        # Extrai o nome do arquivo e cria um identificador único (sufixo)
        # Exemplo: de "camara_db_leg56.json" para "leg56"
        nome_base = os.path.basename(arquivo)
        sufixo = nome_base.replace("camara_db_", "").replace(".json", "")
        
        # Define o caminho do arquivo de cache (.pkl) onde os embeddings serão salvos
        arquivo_pkl = os.path.join(config.PASTA_DADOS, f"keywords_embeddings_{sufixo}.pkl")

        print(f"\nProcessando legislatura: {sufixo}")

        # Abre e carrega os dados brutos dos projetos de lei
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)

        # Extrai a lista de palavras-chave (keywords) dos dados carregados
        keywords = extrair_keywords(dados)

        # Se o arquivo não contiver keywords, pula para a próxima legislatura
        if not keywords:
            print("Nenhuma keyword encontrada. Pulando.")
            continue

        # Flag de controle para decidir se a IA precisa processar os dados
        precisa_atualizar = True

        # 🔹 LÓGICA DE CACHE:
        # Verifica se já existe um arquivo de embeddings salvo para esta legislatura
        if os.path.exists(arquivo_pkl):
            try:
                # Carrega o cache existente
                with open(arquivo_pkl, "rb") as f:
                    cache = pickle.load(f)

                # Validação estrutural rigorosa do cache:
                # 1. Confirma se o arquivo é um dicionário
                # 2. Confirma se possui as chaves necessárias
                # 3. Confirma se a quantidade de keywords no cache é igual à extraída agora
                if (
                    isinstance(cache, dict)
                    and "keywords_texto" in cache
                    and "keywords_vectors" in cache
                    and len(cache["keywords_texto"]) == len(keywords)
                ):
                    print(f"Cache válido para {sufixo}. Pulando vetorização.")
                    precisa_atualizar = False # Evita rodar a IA desnecessariamente

            except Exception:
                # Se o arquivo existir mas estiver quebrado, força a recriação
                print("Cache corrompido ou inválido. Regerando.")

        # Se não houver cache válido, inicia o processamento pesado com a IA
        if precisa_atualizar:
            print(f"Vetorizando {len(keywords)} tags...")

            # Gera as representações matemáticas (embeddings) das palavras-chave
            embeddings = model.encode(
                keywords,
                batch_size=64,           # Processa em lotes para não estourar a memória
                show_progress_bar=True,  # Mostra a barra de progresso no terminal
                convert_to_tensor=True   # Mantém os dados no formato otimizado do PyTorch
            )

            # Salva o novo resultado no arquivo de cache (.pkl)
            with open(arquivo_pkl, "wb") as f:
                pickle.dump(
                    {
                        "keywords_texto": keywords,
                        # .cpu() move os dados da placa de vídeo (se usada) para a RAM padrão, 
                        # garantindo que o arquivo salvo possa ser lido em qualquer computador
                        "keywords_vectors": embeddings.cpu() 
                    },
                    f
                )

            print(f"Salvo: {arquivo_pkl}")