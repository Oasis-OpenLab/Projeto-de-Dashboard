import json
import pickle
import os
import glob
import config
from sentence_transformers import SentenceTransformer
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

# ==================== INÍCIO DAS ALTERAÇÕES: TERMINAL (CLI) E MODO DE EXECUÇÃO ====================
import argparse

def processar_keywords(modo="incremental", legislatura="leg57"):
    print("Carregando modelo de IA...", flush=True)
    model = get_model()

    if modo == "incremental":
        arquivos_db = [os.path.join(config.PASTA_DADOS, f"camara_db_{legislatura}.json")]
    else:
        padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
        arquivos_db = glob.glob(padrao_busca)

    for arquivo in arquivos_db:
        if not os.path.exists(arquivo):
            continue

        nome_base = os.path.basename(arquivo)
        sufixo = nome_base.replace("camara_db_", "").replace(".json", "")
        arquivo_pkl = os.path.join(config.PASTA_DADOS, f"keywords_embeddings_{sufixo}.pkl")

        print(f"\nProcessando keywords da legislatura: {sufixo}", flush=True)

        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)

        keywords = extrair_keywords(dados)
        if not keywords:
            print("Nenhuma keyword encontrada. Pulando.", flush=True)
            continue

        precisa_atualizar = True
        if modo == "incremental" and os.path.exists(arquivo_pkl):
            try:
                with open(arquivo_pkl, "rb") as f:
                    cache = pickle.load(f)
                if (
                    isinstance(cache, dict)
                    and "keywords_texto" in cache
                    and "keywords_vectors" in cache
                    and len(cache["keywords_texto"]) == len(keywords)
                ):
                    print(f"Cache válido para {sufixo}. Pulando vetorização.", flush=True)
                    precisa_atualizar = False
            except Exception:
                print("Cache corrompido ou inválido. Regerando.", flush=True)

        if precisa_atualizar:
            print(f"Vetorizando {len(keywords)} tags...", flush=True)
            embeddings = model.encode(
                keywords,
                batch_size=64,
                show_progress_bar=True,
                convert_to_tensor=True
            )

            with open(arquivo_pkl, "wb") as f:
                pickle.dump(
                    {
                        "keywords_texto": keywords,
                        "keywords_vectors": embeddings.cpu()
                    },
                    f
                )

            print(f"Salvo: {arquivo_pkl}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerador de Embeddings de Keywords")
    parser.add_argument(
        "--modo", 
        choices=["full", "incremental"], 
        default="incremental",
        help="Escolha 'full' para regerar keywords de todas as legislaturas ou 'incremental' para a atual."
    )
    parser.add_argument(
        "--leg", 
        default="leg57",
        help="Legislatura a ser processada no modo incremental (padrão: leg57)."
    )
    args = parser.parse_args()

    print(f"=== INICIANDO GERADOR DE KEYWORDS (MODO: {args.modo.upper()}) ===", flush=True)
    processar_keywords(modo=args.modo, legislatura=args.leg)
# ==================== FIM DAS ALTERAÇÕES: TERMINAL (CLI) E MODO DE EXECUÇÃO ====================