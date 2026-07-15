import os
import json
import config
from sentence_transformers import SentenceTransformer, util
from utils_legislativo import limpar_ementa_para_vetorizacao
from embeddings import get_model
import cohere

# Configurações de teste
NORMA_TESTE = "PL 2338/2023" # Altere conforme necessário
TEMA_TESTE = "inteligência artificial"

def diagnosticar():
    print(f"--- INICIANDO DIAGNÓSTICO PARA: {NORMA_TESTE} ---")
    
    # 1. Localizar a proposição no seu cache local
    padrao = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    import glob
    arquivos = glob.glob(padrao)
    
    proposicao = None
    for arq in arquivos:
        with open(arq, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            for p in dados:
                norma = f"{p['siglaTipo']} {p['numero']}/{p['ano']}"
                if norma.strip() == NORMA_TESTE:
                    proposicao = p
                    break
    
    if not proposicao:
        print(f"ERRO: Proposição {NORMA_TESTE} não encontrada nos arquivos JSON.")
        return

    # 2. Teste de Limpeza
    ementa_orig = proposicao.get('ementa', '')
    ementa_limpa = limpar_ementa_para_vetorizacao(ementa_orig)
    print(f"\n[A] Limpeza de Ementa:")
    print(f"Original: {ementa_orig[:100]}...")
    print(f"Limpo:    {ementa_limpa[:100]}...")

    # 3. Teste de Embedding (Bi-Encoder)
    model = get_model() # Carrega o modelo definido em config[cite: 4]
    emb_query = model.encode(TEMA_TESTE, convert_to_tensor=True)
    emb_ementa = model.encode(ementa_limpa, convert_to_tensor=True)
    score_sem = util.cos_sim(emb_query, emb_ementa).item()
    print(f"\n[B] Similaridade Semântica (Bi-Encoder): {score_sem:.4f}")

    # 4. Teste de Keywords
    keywords = proposicao.get('keywords') or proposicao.get('indexacao', '')
    print(f"\n[C] Keywords encontradas: {keywords}")

    # 5. Teste de Re-ranking (IA Especialista)
    if config.EXECUTAR_RERANKING:
        co = cohere.Client(config.COHERE_API_KEY)
        doc = f"PROJETO: {NORMA_TESTE} | EMENTA: {ementa_limpa}"
        res = co.rerank(query=TEMA_TESTE, documents=[doc], model="rerank-multilingual-v3.0", top_n=1)
        print(f"\n[D] Score de Relevância (Cohere IA): {res.results[0].relevance_score:.4f}")

if __name__ == "__main__":
    diagnosticar()

