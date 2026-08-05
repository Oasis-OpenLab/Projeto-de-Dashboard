"""
Motor de Busca e Filtragem Híbrida (V3 Final).

Responsável por cruzar as consultas de pesquisa do usuário com o banco de dados local.
Implementa uma arquitetura em duas fases (Two-Stage Retrieval):
1. Recuperação Preliminar (Bi-Encoder): Usa Cosine Similarity local para achar candidatos.
2. Re-ranking (Cross-Encoder): Usa a API da Cohere AI para reordenar os Top K resultados
   com base no contexto profundo da relação entre a pergunta e o projeto.
"""
import json
import csv
import os
import pickle
import glob
from sentence_transformers import SentenceTransformer, util
from datetime import datetime 
import config
from utils_legislativo import limpar_ementa_para_vetorizacao, limpar_texto_basico, validar_tag
from embeddings import get_model, get_or_create_embeddings

import cohere
import config
import pandas as pd

# Inicializa o cliente da Cohere usando a chave segura do Streamlit
co = cohere.Client(config.COHERE_API_KEY)

# =====================================================================
# NOVO MÓDULO: CÁLCULO DE TRAÇÃO LEGISLATIVA (SCORE POLÍTICO)
# =====================================================================
def calcular_score_politico(proposicao):
    """
    Calcula a temperatura política do projeto baseada na velocidade 
    de tramitação e na situação crítica atual.
    Retorna um valor normalizado (0 a 1).
    """
    status_data = proposicao.get('statusProposicao') or {}
    situacao_atual = str(status_data.get('descricaoSituacao') or '').lower()
    
    # 1. Filtro de Morte Política
    if any(morte in situacao_atual for morte in ["arquivad", "retirad", "devolvid"]):
        return 0.0

    # 2. Total de movimentações
    # O "atalho": A chave 'sequencia' guarda o número da tramitação mais recente.
    # Ex: se a sequência for 45, o projeto teve 45 movimentações.
    total_movimentacoes = status_data.get('sequencia', 0)
    
    if total_movimentacoes == 0:
        return 0.0
        
    # 3. Cálculo de Tempo de Vida (Idade do Projeto)
    data_inicio_str = proposicao.get('dataApresentacao', '')[:10]
    data_fim_str = status_data.get('dataHora', '')[:10]
    
    try:
        if data_inicio_str:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d')
        else:
            data_inicio = datetime(2015, 1, 1)
            
        if data_fim_str:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d')
        else:
            data_fim = datetime.now()
    except Exception:
        data_inicio = datetime(2015, 1, 1)
        data_fim = datetime.now()
        
    dias_vida = max((data_fim - data_inicio).days, 1) # Evita divisão por zero
    meses_vida = max(dias_vida / 30.0, 1.0)
    
    velocidade = total_movimentacoes / meses_vida
    
    # Normalização suave: Assumimos que 4 tramitações por mês é o teto "muito rápido" (score 1.0)
    score_velocidade = velocidade / 4.0
    
    # 4. Bônus de Situação (Qualidade da Movimentação)
    multiplicador = 1.0
    if "urgência" in situacao_atual or "pronto para pauta" in situacao_atual:
        multiplicador = 1.5
    elif "aprovado" in situacao_atual or "remetido" in situacao_atual or "sanção" in situacao_atual:
        multiplicador = 2.0
    elif "parecer" in situacao_atual and "aguardando" not in situacao_atual:
        multiplicador = 1.3
        
    score_final_politico = score_velocidade * multiplicador 
    return score_final_politico

# =====================================================================
# RERANKING
# =====================================================================
def aplicar_reranking(query, contexto_usuario, resultados_preliminares):
    """
    Refina a ordenação dos melhores candidatos utilizando a IA da Cohere
    E a Tração Legislativa.
    
    Cria um prompt enriquecido com a Norma, Ementa e Indexação e submete ao 
    modelo Rerank da Cohere. Isso corrige casos onde uma busca por palavras tem 
    alta similaridade matemática, mas baixo sentido prático (falsos positivos).

    Args:
        query (str): A pesquisa original digitada pelo usuário.
        contexto_usuario (str): Contexto extra fornecido pelo usuário.
        resultados_preliminares (list): Dicionário contendo os projetos pré-selecionados.

    Returns:
        list: Lista de projetos reordenados de acordo com o score de relevância da Cohere.
    """
    if not resultados_preliminares:
        return []

    # passando pouco contexto apra a cohere - ementa limpa
    textos_para_analise = []
    for r in resultados_preliminares:
        # Aplica a limpeza para remover "Dispõe sobre", "Altera a lei...", etc.
        ementa_limpa = limpar_ementa_para_vetorizacao(r['Ementa'])
        # Enviamos apenas a norma e a ementa limpa; removemos a indexação para evitar ruído
        textos_para_analise.append(f"PROJETO: {r['Norma']} | EMENTA: {ementa_limpa}")
    
    try:
        # ---------------------------------------------------------
        # EXPANSÃO DE CONSULTA (QUERY EXPANSION) DINÂMICA
        # ---------------------------------------------------------
        if contexto_usuario and contexto_usuario.strip():
            query_enriquecida = f"Tema: {query}. Foco desejado do usuário: {contexto_usuario}"
        else:
            query_enriquecida = query 
        
        rerank_response = co.rerank(
            query=query_enriquecida,
            documents=textos_para_analise,
            top_n=config.TOP_K_RERANK,
            model="rerank-multilingual-v3.0"
        )

        resultados_refinados = []
        for hit in rerank_response.results:
            # Recuperamos o projeto original pelo índice retornado pela API
            nota_cohere = hit.relevance_score
            projeto = resultados_preliminares[hit.index]

            # Recupera o score político salvo no processamento inicial
            score_politico = projeto.get('Score Politico', 0.0)

            # ---------------------------------------------------------
            # ENSEMBLE RANKING (MISTURA DE CÉREBROS) PARAMETRIZADO
            # ---------------------------------------------------------
            score_bi_encoder = float(projeto.get('Score Semantico (IA)', 0.0))
            nota_semantica_mista = (nota_cohere * config.PESO_COHERE_ENSEMBLE) + (score_bi_encoder * config.PESO_BIENCODER_ENSEMBLE)

            # O VETO SEMÂNTICO PARAMETRIZADO
            if nota_semantica_mista < config.VETO_SEMANTICO_MINIMO:
                score_politico = 0.0

            # CÁLCULO DO SCORE DO PAINEL OASIS (Semântica Mista + Política)
            nota_final = (nota_semantica_mista * config.PESO_SEMANTICO_FINAL) + (score_politico * config.PESO_POLITICO_FINAL)

            # Atualizamos o score com a nota de relevância da IA Especialista
            projeto['Score Final'] = f"{nota_final:.4f}"
            projeto['Metodo'] = "IA Especialista (Rerank) + Tração"
            
            # Guardamos o valor numérico para que a ordenação seja mantida
            projeto['raw_score'] = nota_final

            # Opcional: Manter visível o breakdown das notas
            projeto['Score Semantico (IA)'] = f"{nota_cohere:.4f}"
            projeto['Score Politico (Tracao)'] = f"{score_politico:.4f}"

            resultados_refinados.append(projeto)
        
        # Reordena a lista baseada na nova nota combinada
        resultados_refinados.sort(key=lambda x: x['raw_score'], reverse=True)  
        return resultados_refinados

    except Exception as e:
        # Se a API falhar (ex: sem internet), o sistema não trava
        print(f"⚠️ Aviso: Falha no Re-ranking ({e}). Mantendo ordem original.")
        return resultados_preliminares

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

    A fórmula do Score Híbrido combina:
    A) A Média Ponderada da Similaridade do Cosseno entre a query principal e secundária.
    B) Um Boost (Bônus) de pontuação baseado na correspondência exata de Keywords.
    
    Filtra projetos que não atinjam o limite mínimo (Threshold) configurado.

    Args:
        dados (list): Projetos brutos em formato JSON.
        pkl_data (dict): Cache de keywords vetorizadas daquela legislatura.
        query_embedding (Tensor): Vetor matemático da pesquisa principal do usuário.
        query_embedding_secundaria (Tensor ou None): Vetor da pesquisa secundária.
        termos_usuario (list): Palavras da pesquisa divididas para busca de match exato.
        model (SentenceTransformer): Modelo de IA ativo.
        sufixo_leg (str): Identificador do lote (ex: 'leg56').

    Returns:
        list: Projetos filtrados e formatados, prontos para exportação/re-ranking.
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

        #Excluir Arquivados
        # Verificamos se 'statusProposicao' é um dicionário antes de acessar a descrição
        status_data = p.get('statusProposicao')
        if isinstance(status_data, dict):
            # Convertemos para string e garantimos que não seja None antes de aplicar .lower()
            situacao_projeto = str(status_data.get('descricaoSituacao') or '').lower()
        else:
            situacao_projeto = ''
            
        if "arquiv" in situacao_projeto:
            continue

        # ---------------------------------------------------------
        # NOVO: CHAVE MESTRA DA TRAÇÃO POLÍTICA (LIGA/DESLIGA)
        # ---------------------------------------------------------
        if config.HABILITAR_TRACAO_POLITICA:
            score_pol = calcular_score_politico(p)
        else:
            score_pol = 0.0

        # ----------------------------
        # BLOCO 4 — BOOST POR KEYWORD E CORTE DINÂMICO
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
            # ---------------------------------------------------------
            # CORTE MAIS RIGOROSO (PARAMETRIZADO)
            # ---------------------------------------------------------
            limite_corte = config.THRESHOLD_SEMANTICO_MINIMO + config.PENALIDADE_SEM_KEYWORD
        elif termos_encontrados == 1:
            score_kw, boost_ativo = 0.5, "PARCIAL (1 Termo)"
            limite_corte = config.THRESHOLD_SEMANTICO_MINIMO
        else:
            score_kw, boost_ativo = 1.0, f"TOTAL ({termos_encontrados} Termos)"
            limite_corte = config.THRESHOLD_SEMANTICO_MINIMO
            
        # ---------------------------------------------------------
        # APLICAÇÃO DO CORTE DINÂMICO
        # ---------------------------------------------------------
        if score_sem_principal < limite_corte:
            continue
            
        # ----------------------------
        # BLOCO 5 — SCORE HÍBRIDO
        # ----------------------------
        final = (score_sem_combinado * config.PESO_SEMANTICO) + (score_kw * config.PESO_KEYWORD)
        
        if final >= config.FILTRO_THRESHOLD:
            # Mistura do Termômetro Político caso o Re-ranking esteja desligado
            # (Se o re-ranking estiver ligado, essa nota será sobrescrita na API)
            nota_painel_final = (final * config.PESO_SEMANTICO_FINAL) + (score_pol * config.PESO_POLITICO_FINAL)

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
                "ID Proposicao": p.get('id', ''),
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
                "Score Final": f"{nota_painel_final:.4f}",
                "Score Semantico (IA)": f"{final:.4f}",
                "Score Politico (Tracao)": f"{score_pol:.4f}",
                "Boost Keyword": boost_ativo,
                "Metodo": "Bi-Encoder (Local) + Tração",
                "raw_score": nota_painel_final,
                
                # ---> A LINHA QUE FALTAVA PARA A COHERE LER O NÚMERO <---
                "Score Politico": score_pol
            })
            
    return lote_resultados

# ==========================================
# FUNÇÃO PRINCIPAL CHAMADA PELO DASHBOARD
# ==========================================
def executar_filtragem(consulta_usuario, consulta_secundaria, contexto_usuario, model):
    """
    Recebe o tema digitado pelo usuário no Streamlit e o modelo de IA já carregado na memória RAM.
    Filtra os 50.000 projetos e gera o CSV atualizado em poucos segundos.
    Orquestrador principal do Motor de Busca.

    Executa o fluxo completo:
    1. Vetoriza em tempo real o input do usuário.
    2. Itera sobre as bases locais (JSON + PKL) filtrando com Cosine Similarity.
    3. Ordena e envia os 50 melhores (Top K) para o Re-ranking da API Cohere.
    4. Gera o arquivo CSV final formatado para consumo do Dashboard SQL.

    Args:
        consulta_usuario (str): Tema principal da pesquisa.
        consulta_secundaria (str): Tema secundário ou filtro extra da pesquisa.
        contexto_usuario (str): Instrução direcionada para o modelo da Cohere.
        model (SentenceTransformer): O modelo de embeddings já carregado na memória.

    Returns:
        list: A lista final de dicionários com os resultados refinados.
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

    # 4. Ordenação e Re-ranking
    # Ordena o que o Bi-Encoder achou (Top K iniciais)
    todos_resultados.sort(key=lambda x: x['raw_score'], reverse=True)

    if config.EXECUTAR_RERANKING:
        # Recorte para o Top K definido no config.py
        candidatos = todos_resultados[:config.TOP_K_RERANK]
        print(f"Refinando os {len(candidatos)} melhores com IA Especialista...")
        resultados_finais = aplicar_reranking(consulta_usuario, contexto_usuario, candidatos)
    else:
        print("Re-ranking desativado. Mantendo a ordenação do Bi-Encoder.")
        # Se desativado, o resultado final é a própria lista ordenada pelo Bi-Encoder
        resultados_finais = todos_resultados

    # 5. Preparação para Salvamento
    colunas = [
        "ID Proposicao", "Norma", "Descricao da Sigla", "Data de Apresentacao", "Autor", "Partido", "Ementa", 
        "Link Documento PDF", "Link Página Web", "Indexacao", "Último Estado", "Data Último Estado", 
        "Situação", "Score Final", "Score Semantico (IA)", "Score Politico (Tracao)", "Boost Keyword", "Metodo"
    ]

    # Garante que a pasta existe
    pasta_destino = os.path.dirname(NOME_ARQUIVO_SAIDA)
    if pasta_destino and not os.path.exists(pasta_destino): 
        os.makedirs(pasta_destino)

    # 6. Salva o CSV com os resultados REORDENADOS (resultados_finais)
    # Usamos o encoding utf-8-sig para que o Excel abra os acentos corretamente
    with open(NOME_ARQUIVO_SAIDA, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=colunas, extrasaction='ignore', delimiter=';')
        writer.writeheader()
        writer.writerows(resultados_finais) # <-- Importante: salvando a lista refinada
    
    print(f"[SUCESSO] Re-ranking concluído. {len(resultados_finais)} projetos refinados salvos.")
    return resultados_finais

# ==========================================================
# BLOCO DE EXECUÇÃO DIRETA (Garante o funcionamento em background)
# ==========================================================
if __name__ == "__main__":
    # Carrega o modelo de IA apenas se o script for chamado diretamente
    print("🧠 Inicializando modelo de IA para filtragem semântica...")
    model = SentenceTransformer(config.MODELO_NOME, device=config.dispositivo)
    
    # Recupera os temas salvos temporariamente pelo Streamlit
    caminho_p1 = 'banco_de_dados_local/pesquisa1.txt'
    caminho_p2 = 'banco_de_dados_local/pesquisa2.txt'
    caminho_contexto = 'banco_de_dados_local/pesquisa_contexto.txt'
    
    tema_principal = ""
    tema_secundario = ""
    contexto_usuario = ""
    
    if os.path.exists(caminho_p1):
        with open(caminho_p1, 'r', encoding='utf-8') as arquivo:
            tema_principal = arquivo.readline().strip()
            
    if os.path.exists(caminho_p2):
        with open(caminho_p2, 'r', encoding='utf-8') as arquivo:
            tema_secundario = arquivo.readline().strip()
            
    if os.path.exists(caminho_contexto):
        with open(caminho_contexto, 'r', encoding='utf-8') as arquivo:
            contexto_usuario = arquivo.readline().strip()
            
    if tema_principal:
        # Executa o motor completo e gera o novo CSV refinado
        executar_filtragem(tema_principal, tema_secundario, contexto_usuario, model)
    else:
        print("⚠️ Erro: Nenhum tema principal localizado em pesquisa1.txt")