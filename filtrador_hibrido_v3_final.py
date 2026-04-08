import json
import csv
import os
import pickle
import glob
from sentence_transformers import SentenceTransformer, util
import config
from utils_legislativo import limpar_ementa_para_vetorizacao, limpar_texto_basico, validar_tag
from embeddings import get_model, get_or_create_embeddings

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
    import os
    import config
    from sentence_transformers import util
    # Certifique-se de que validar_tag está importado ou definido no escopo
    
    # ----------------------------
    # BLOCO 1 e 2 — EMBEDDINGS VIA MÓDULO EXTERNO
    # ----------------------------
    ementa_embeddings = get_or_create_embeddings(
        dados=dados,
        sufixo_leg=sufixo_leg,
        model=model
    )

    # CORREÇÃO CRÍTICA: Garantir que o tensor seja Float para evitar RuntimeError: Got Long
    if ementa_embeddings is not None and not ementa_embeddings.is_floating_point():
        ementa_embeddings = ementa_embeddings.float()

    # ----------------------------
    # BLOCO 3 — SIMILARIDADE SEMÂNTICA
    # ----------------------------
    # 1. Afinidade com o tema principal
    cos_scores_principal = util.cos_sim(query_embedding, ementa_embeddings)[0]
    
    # 2. Afinidade com o tema da query secundaria
    if query_embedding_secundaria is not None:
        cos_scores_secundaria = util.cos_sim(query_embedding_secundaria, ementa_embeddings)[0]
    else:
        cos_scores_secundaria = cos_scores_principal
    
    lote_resultados = []

    # Itera sobre cada proposição
    for idx, score_tensor in enumerate(cos_scores_principal):
        score_sem_principal = float(score_tensor)
        score_sem_secundaria = float(cos_scores_secundaria[idx])

        # REGRA DE CORTE DUPLA
        if score_sem_principal < config.THRESHOLD_SEMANTICO_MINIMO:
            continue
        if query_embedding_secundaria is not None and score_sem_secundaria < config.THRESHOLD_SEMANTICO_MINIMO_SECUNDARIA:
            continue

        # MÉDIA PONDERADA
        score_sem_combinado = ((score_sem_principal * config.PESO_QUERY_PRINCIPAL) + 
                               (score_sem_secundaria * config.PESO_QUERY_SECUNDARIA))

        p = dados[idx]

        # ----------------------------
        # BLOCO 4 — BOOST POR KEYWORD
        # ----------------------------
        raw_tags = p.get('keywords') or p.get('indexacao')
        tags_projeto_limpas = set()

        if raw_tags:
            # Normalização de separadores
            for t in raw_tags.replace(';', ',').split(','):
                # validar_tag deve estar acessível aqui
                tag_valida = validar_tag(t) if 'validar_tag' in globals() else t.strip().lower()
                if tag_valida: tags_projeto_limpas.add(tag_valida)

        termos_encontrados = 0
        if termos_usuario and tags_projeto_limpas:
            for tu in termos_usuario:
                if any(f" {tu.lower()} " in f" {tp.lower()} " for tp in tags_projeto_limpas):
                    termos_encontrados += 1
        
        if termos_encontrados == 0:
            score_kw, boost_ativo = 0.0, "NAO"
        elif termos_encontrados == 1:
            score_kw, boost_ativo = 0.5, "PARCIAL (1 Termo)"
        else:
            score_kw, boost_ativo = 1.0, f"TOTAL ({termos_encontrados} Termos)"
            
        # ----------------------------
        # BLOCO 5 — SCORE HÍBRIDO
        # ----------------------------
        final = (score_sem_combinado * config.PESO_SEMANTICO) + (score_kw * config.PESO_KEYWORD)
        
        if final >= config.FILTRO_THRESHOLD:
            # ----------------------------
            # BLOCO 6 — METADADOS E STATUS
            # ----------------------------
            meta = {'situacao': 'Tramitando', 'ultimo_estado': '', 'data_ultimo': ''}
            if 'statusProposicao' in p:
                st_data = p['statusProposicao']
                meta['situacao'] = st_data.get('descricaoSituacao', 'Tramitando')
                meta['ultimo_estado'] = st_data.get('descricaoTramitacao', '')
                meta['data_ultimo'] = st_data.get('dataHora', '')

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
                "Data Último Estado": meta['data_ultimo'][:10] if meta['data_ultimo'] else '',
                "Situação": meta['situacao'],
                "Score Final": f"{final:.4f}",
                "Boost Keyword": boost_ativo,
                "Similaridade Semantica": f"{score_sem_combinado:.4f}",
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

