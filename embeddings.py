import os
import json
import pickle
import glob
from sentence_transformers import SentenceTransformer
import config
from utils_legislativo import limpar_ementa_para_vetorizacao


# ==========================================================
# FUNÇÃO 1 — Carregamento único do modelo (usado pelo app)
# ==========================================================
def get_model():
    return SentenceTransformer(
        config.MODELO_NOME,
        device=config.dispositivo
    )


# ==========================================================
# FUNÇÃO 2 — Carrega cache ou gera embeddings (usado no app)
# ==========================================================
def get_or_create_embeddings(dados, sufixo_leg, model):
    """
    Carrega embeddings do cache se existir e estiver válido.
    Caso contrário, gera novos embeddings e salva.
    """

    arquivo_cache = os.path.join(
        config.PASTA_DADOS,
        f"cache_ementas_{sufixo_leg}.pkl"
    )

    # 1️⃣ Tenta carregar cache
    if os.path.exists(arquivo_cache):
        with open(arquivo_cache, 'rb') as f:
            cache_data = pickle.load(f)

        # Segurança: valida tamanho
        if len(cache_data) == len(dados):
            print(f"Cache reutilizado para {sufixo_leg}.")
            return cache_data

        print(f"Cache inválido para {sufixo_leg} (tamanho diferente).")

    # 2️⃣ Gera embeddings se não houver cache válido
    print(f"Gerando embeddings para {sufixo_leg}...")

    ementas_limpas = [
        limpar_ementa_para_vetorizacao(p.get('ementa', ''))
        for p in dados
    ]

    embeddings = model.encode(
        ementas_limpas,
        batch_size=64,
        convert_to_tensor=True,
        show_progress_bar=True
    )

    with open(arquivo_cache, 'wb') as f:
        pickle.dump(embeddings.cpu(), f)

    print(f"✔ Cache atualizado para {sufixo_leg}")

    return embeddings.cpu()


# ==========================================================
# FUNÇÃO 3 — Script offline de geração completa
# ==========================================================
def gerar_embeddings_para_legislatura(model, arquivo_json):
    nome_base = os.path.basename(arquivo_json)
    sufixo_leg = nome_base.replace("camara_db_", "").replace(".json", "")

    print(f"\nProcessando {sufixo_leg}...")

    with open(arquivo_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    ementas_limpas = [
        limpar_ementa_para_vetorizacao(p.get('ementa', ''))
        for p in dados
    ]

    embeddings = model.encode(
        ementas_limpas,
        batch_size=64,
        convert_to_tensor=True,
        show_progress_bar=True
    )

    caminho_saida = os.path.join(
        config.PASTA_DADOS,
        f"cache_ementas_{sufixo_leg}.pkl"
    )

    with open(caminho_saida, 'wb') as f:
        pickle.dump(embeddings, f)

    print(f"✔ Embeddings salvos em {caminho_saida}")
    print(f"Total de projetos: {len(dados)}")


def main():
    print("Carregando modelo...")

    model = get_model()

    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_json = glob.glob(padrao_busca)

    if not arquivos_json:
        print("Nenhum JSON encontrado.")
        return

    for arquivo_json in arquivos_json:
        gerar_embeddings_para_legislatura(model, arquivo_json)

    print("\n✅ Processo finalizado com sucesso.")


if __name__ == "__main__":
    main()