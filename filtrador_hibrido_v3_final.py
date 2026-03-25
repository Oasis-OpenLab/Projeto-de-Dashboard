import json
import csv
import os
import pickle
import glob
from sentence_transformers import SentenceTransformer, util
import config
from utils_legislativo import limpar_ementa_para_vetorizacao, limpar_texto_basico, validar_tag

NOME_ARQUIVO_SAIDA = os.path.join(config.PASTA_CSV, "proposicoes_camara_resumo.csv")

def processar_lote(dados, pkl_data, query_embedding, query_embedding_secundaria, termos_usuario, model, sufixo_leg):
    """
    Processa um lote correspondente a UMA legislatura específica.

    Responsabilidades:
    1) Carregar ou gerar embeddings das ementas (cache por legislatura).
    2) Calcular similaridade semântica entre consulta do usuário e cada ementa.
    3) Aplicar reforço (boost) baseado em palavras-chave (híbrido).
    4) Calcular score final ponderado.
    5) Retornar apenas projetos que ultrapassem o threshold configurado.
    """

    # Arquivo de cache dos embeddings das ementas e o JSON base dessa legislatura.
    arquivo_cache = os.path.join(config.PASTA_DADOS, f"cache_ementas_{sufixo_leg}.pkl")
    arquivo_json = os.path.join(config.PASTA_DADOS, f"camara_db_{sufixo_leg}.json")
    
    ementa_embeddings = None
    
    # ----------------------------
    # BLOCO 1 — USO DE CACHE INTELIGENTE
    # ----------------------------
    # Pega a data de modificação do JSON bruto para ver se tem projetos novos
    json_mtime = os.path.getmtime(arquivo_json)

    # Invalidação Inteligente: Só carrega o cache se ele for mais recente que o banco JSON
    if os.path.exists(arquivo_cache):
        pkl_mtime = os.path.getmtime(arquivo_cache)
        # Se o cache é mais novo que o arquivo JSON, reaproveitamos os vetores
        if pkl_mtime > json_mtime:
            with open(arquivo_cache, 'rb') as f: cache_data = pickle.load(f)
            # Segurança extra: Só reutiliza se o número de embeddings for igual ao número de projetos.
            if len(cache_data) == len(dados): 
                ementa_embeddings = cache_data

    # ----------------------------
    # BLOCO 2 — GERAÇÃO DE EMBEDDINGS (SE O CACHE ESTIVER INVÁLIDO)
    # ----------------------------
    if ementa_embeddings is None:
        print(f"Gerando novos vetores de ementas para {sufixo_leg} (Base atualizada/Projetos novos)...")
        # Limpa cada ementa antes de vetorização
        ementas_limpas = [limpar_ementa_para_vetorizacao(p.get('ementa', '')) for p in dados]
        # Gera embeddings em batch (mais eficiente)
        ementa_embeddings = model.encode(ementas_limpas, batch_size=64, convert_to_tensor=True, show_progress_bar=True)
        # Salva cache atualizado para execuções futuras
        with open(arquivo_cache, 'wb') as f: pickle.dump(ementa_embeddings, f)

    # ----------------------------
    # BLOCO 3 — SIMILARIDADE SEMÂNTICA
    # ----------------------------
    # Calcula similaridade de cosseno entre query_embedding e todos os embeddings das ementas
    # 1. Afinidade com o tema principal
    cos_scores_principal = util.cos_sim(query_embedding, ementa_embeddings)[0]
    # 2. Afinidade com o tema da query secundaria
    if (query_embedding_secundaria) is not None:
        cos_scores_secundaria = util.cos_sim(query_embedding_secundaria, ementa_embeddings)[0]
    else:
        # Se não tem query secundária, ela apenas "espelha" a query principal sem reprocessar
        cos_scores_secundaria = cos_scores_principal

    lote_resultados = []

    # Itera sobre cada proposição
    for idx, score_tensor in enumerate(cos_scores_principal):
        score_sem_principal = float(score_tensor)
        score_sem_secundaria = float(cos_scores_secundaria[idx]) # Devido ao espelhamento, podemos ter score_sem_secundaria == score_sem_principal, caso query secundaria seja nula

        # REGRA DE CORTE DUPLA:
        # Se não atingir mínimo semântico, ignora imediatamente.
        if score_sem_principal < config.THRESHOLD_SEMANTICO_MINIMO:
            continue
        if query_embedding_secundaria is not None and score_sem_secundaria < config.THRESHOLD_SEMANTICO_MINIMO_SECUNDARIA:
            continue

        # MÉDIA PONDERADA (Ex: 70% de peso ao tema principal e 30% ao secundário)
        score_sem_combinado = ((score_sem_principal * config.PESO_QUERY_PRINCIPAL) + (score_sem_secundaria * config.PESO_QUERY_SECUNDARIA))

        p = dados[idx]

        # ----------------------------
        # BLOCO 4 — BOOST POR KEYWORD (NOVA LÓGICA PROGRESSIVA)
        # ----------------------------
        # Aqui, em vez de dar uma nota fixa 1.0 se achar qualquer palavra,
        # nós contamos quantas palavras exatas o projeto tem.
        
        raw_tags = p.get('keywords') or p.get('indexacao')
        tags_projeto_limpas = set()

        # Se houver indexação, normaliza
        if raw_tags:
            for t in raw_tags.replace(';', ',').split(','):
                tag_valida = validar_tag(t)
                if tag_valida: tags_projeto_limpas.add(tag_valida)

        termos_encontrados = 0
        
        # Compara termos da consulta do usuário com as tags limpas do projeto
        if termos_usuario and tags_projeto_limpas:
            for tu in termos_usuario:
                # Verifica quantos termos isolados existem nas tags
                if any(f" {tu} " in f" {tp} " for tp in tags_projeto_limpas):
                    termos_encontrados += 1
        
        # Aplica a pontuação com base na quantidade de acertos (Evita falsos positivos como "lago artificial")
        if termos_encontrados == 0:
            score_kw, boost_ativo = 0.0, "NAO"
        elif termos_encontrados == 1:
            score_kw, boost_ativo = 0.5, "PARCIAL (1 Termo)" # Peso pela metade
        else:
            score_kw, boost_ativo = 1.0, f"TOTAL ({termos_encontrados} Termos)" # Boost máximo
            
        # ----------------------------
        # BLOCO 5 — SCORE HÍBRIDO
        # ----------------------------
        final = (score_sem_combinado * config.PESO_SEMANTICO) + (score_kw * config.PESO_KEYWORD)
        
        if final >= config.FILTRO_THRESHOLD:
            # ----------------------------
            # BLOCO 6 — METADADOS
            # ----------------------------
            meta = {'situacao': 'Tramitando', 'ultimo_estado': '', 'data_ultimo': ''}
            # Se houver informações de status
            if 'statusProposicao' in p:
                st = p['statusProposicao']
                meta['situacao'] = st.get('descricaoSituacao', 'Tramitando')
                meta['ultimo_estado'] = st.get('descricaoTramitacao', '')
                meta['data_ultimo'] = st.get('dataHora', '')

            # Monta dicionário final de saída
            lote_resultados.append({
                "Norma": f"{p['siglaTipo']} {p['numero']}/{p['ano']}",
                "Descricao da Sigla": p.get('descricaoTipo', ''),
                "Data de Apresentacao": p.get('dataApresentacao', '')[:10],
                "Autor": p.get('autor_principal_nome', 'N/A'),
                "Partido": p.get('autor_principal_partido', 'N/A'),
                "Ementa": p.get('ementa', '').strip(),
                "Link Documento PDF": p.get('urlInteiroTeor', ''),
                "Link Página Web": p.get('url_pagina_web_oficial', ''),
                "Indexacao": p.get('keywords', p.get('indexacao', '')),
                "Último Estado": meta['ultimo_estado'],
                "Data Último Estado": meta['data_ultimo'][:10],
                "Situação": meta['situacao'],
                "Score Final": f"{final:.4f}",
                "Boost Keyword": boost_ativo,
                "Similaridade Semantica": f"{score_sem_combinado:.4f}",
                # Campo interno para ordenação
                "raw_score": final
            })
    return lote_resultados

# ==========================================
# FUNÇÃO PRINCIPAL CHAMADA PELO DASHBOARD
# ==========================================
def executar_filtragem(consulta_usuario, consulta_secundaria, model):
    """
    Recebe o tema digitado pelo usuário no Streamlit e o modelo de IA já carregado na memória RAM.
    Filtra os 50.000 projetos e gera o CSV atualizado em poucos segundos.
    """
    print(f"\n--- Iniciando Filtragem Híbrida Dinâmica: '{consulta_usuario}' ---")
    
    # 1. Gera o vetor matemático da nova pergunta do usuário na hora
    query_embedding = model.encode(consulta_usuario, convert_to_tensor=True)

    consulta_secundaria_valida = consulta_secundaria and consulta_secundaria.strip()
    query_embedding_secundaria = model.encode(consulta_secundaria, convert_to_tensor=True) if consulta_secundaria_valida else None

    # 2. Extrai os termos puros da pergunta para o sistema de bônus por palavras-chave (Boost)
    consulta_integral = f"{consulta_usuario} {consulta_secundaria}"
    termos_usuario = [t for t in limpar_texto_basico(consulta_integral).upper().split() if len(t) > 3]

    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_db = glob.glob(padrao_busca)
    todos_resultados = []

    # 3. Varre as legislaturas cruzando a nova pergunta com os vetores já salvos
    for arquivo in arquivos_db:
        nome_base = os.path.basename(arquivo)
        sufixo_leg = nome_base.replace("camara_db_", "").replace(".json", "")
        arquivo_pkl = os.path.join(config.PASTA_DADOS, f"keywords_embeddings_{sufixo_leg}.pkl")
        
        if os.path.exists(arquivo_pkl):
            with open(arquivo, 'r', encoding='utf-8') as f: dados = json.load(f)
            with open(arquivo_pkl, 'rb') as f: pkl = pickle.load(f)
            
            # Chama a função processar_lote (que já existe no seu arquivo e continua igual)
            resultados_lote = processar_lote(dados, pkl, query_embedding, query_embedding_secundaria, termos_usuario, model, sufixo_leg)
            todos_resultados.extend(resultados_lote)
            del dados, pkl, resultados_lote

    # 4. Ordena os vencedores pela nota bruta da IA
    todos_resultados = sorted(todos_resultados, key=lambda x: x['raw_score'], reverse=True)

    colunas = [
        "Norma", "Descricao da Sigla", "Data de Apresentacao", "Autor", "Partido", "Ementa", 
        "Link Documento PDF", "Link Página Web", "Indexacao", "Último Estado", "Data Último Estado", 
        "Situação", "Score Final", "Boost Keyword", "Similaridade Semantica"
    ]

    pasta_destino = os.path.dirname(NOME_ARQUIVO_SAIDA)
    if pasta_destino and not os.path.exists(pasta_destino): os.makedirs(pasta_destino)

    # 5. Sobrescreve o arquivo CSV antigo com os novos resultados
    with open(NOME_ARQUIVO_SAIDA, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=colunas, extrasaction='ignore', delimiter=';')
        writer.writeheader()
        writer.writerows(todos_resultados)
    
    print(f"[SUCESSO] Filtragem concluída. {len(todos_resultados)} projetos encontrados para o novo tema.")

# Remova o bloco antigo "if __name__ == '__main__':" que ficava aqui!