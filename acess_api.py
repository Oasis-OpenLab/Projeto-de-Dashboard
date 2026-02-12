import requests
import json
import os
import time
import re
import csv
import sys
import pickle
import numpy as np
import torch
import unicodedata
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer, util
import config

# =============================================================================
# 1. CONFIGURAÇÕES GERAIS
# =============================================================================
CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

# Configuração de Datas para Coleta
# Ajuste DATA_INICIO_COLETA conforme necessário para o histórico desejado
DATA_INICIO_COLETA = config.DATA_INICIO_COLETA
DATA_FIM_COLETA = datetime.now()
TIPOS_DOCUMENTO = ["PL", "PLP", "PEC"]

# Configuração de Busca e Filtro
CONSULTA_USUARIO = config.CONSULTA_USUARIO
MODELO_NOME = config.MODELO_NOME
PESO_SEMANTICO = config.PESO_SEMANTICO
PESO_KEYWORD = config.PESO_KEYWORD    
FILTRO_THRESHOLD = config.FILTRO_THRESHOLD

# Nomes de Arquivos (Internos e de Saída)
NOME_ARQUIVO_BANCO_DADOS = "camara_db_completo_cache.json"
NOME_ARQUIVO_CACHE_IDS = "temp_lista_ids.json"
NOME_ARQUIVO_PKL = "keywords_embeddings.pkl"
ARQUIVO_CACHE_EMB = "cache_ementas_paraphrase.npy"

# IMPORTANTE: Este nome deve ser o mesmo que o main.py espera mover
NOME_ARQUIVO_SAIDA_FINAL_CSV = "proposicoes_camara_resumo.csv"

# =============================================================================
# 2. UTILITÁRIOS LEGISLATIVOS (Integrado do utils_legislativo.py)
# =============================================================================

# Lista Expandida de Stopwords Legislativas
STOPWORDS_LEGISLATIVAS = [
    # Ações Burocráticas
    "dispõe sobre", "dispoe sobre", "trata de", "institui o", "institui a",
    "cria o", "cria a", "estabelece", "normas gerais", "providências",
    "dá outras providências", "da outras providencias", "para os fins",
    "nos termos", "com a finalidade de", "visando a", "a fim de",
    "para dispor sobre", "para prever", "para estender", "para aperfeiçoar",
    
    # Estruturas de Alteração
    "altera a lei", "altera o decreto", "altera os", "altera as",
    "acrescenta", "insere", "modifica", "revoga", "redação dada",
    "redacao dada", "nova redação", "suprime", "veda a", "veda o",
    
    # Referências a Textos Legais (Stopwords Simples)
    "projeto de lei", "pl", "medida provisória", "mpv", "pec",
    "código penal", "código civil", "estatuto", "constituição federal",
    "decreto-lei", "decreto lei", "lei brasileira", "lei de",
    
    # Partes da Lei (Stopwords Simples)
    "caput", "parágrafo único", "paragrafo unico", "inciso", "alínea", 
    "alinea", "item", "dispositivo", "anexo"
]

def limpar_padroes_regex(texto):
    """
    Remove padrões complexos como datas e números de leis usando Regex.
    """
    # 1. Remove referências a leis com números (ex: "Lei nº 12.345", "Lei 12.345")
    texto = re.sub(r'(lei|decreto|medida provisória|resolução|portaria)\s+(n[ºo°]\s*)?[\d\.]+', ' ', texto, flags=re.IGNORECASE)
    
    # 2. Remove datas completas (ex: "de 23 de abril de 2014", "de 7 de dezembro")
    texto = re.sub(r'\bde\s+\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}\b', ' ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bde\s+\d{1,2}\s+de\s+[a-zç]+\b', ' ', texto, flags=re.IGNORECASE)
    
    # 3. Remove referências a Artigos e Parágrafos (ex: "art. 5º", "§ 2º", "art 10")
    texto = re.sub(r'\bart[\.\s]\s*\d+[ºo°]?', ' ', texto, flags=re.IGNORECASE) # Artigos
    texto = re.sub(r'§\s*\d+[ºo°]?', ' ', texto) # Símbolo de parágrafo
    
    # 4. Remove numeração romana de Incisos (ex: "inciso IV", "inciso X")
    texto = re.sub(r'\binciso\s+[ivxlcdm]+\b', ' ', texto, flags=re.IGNORECASE)
    
    return texto

def limpar_ementa_para_vetorizacao(texto):
    if not texto: return ""
    
    # 1. Normalização Básica (Caixa baixa e acentos)
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    
    # 2. Limpeza de Padrões (Datas e Números)
    texto = limpar_padroes_regex(texto)
    
    # 3. Limpeza de Stopwords (Lista Fixa)
    for termo in STOPWORDS_LEGISLATIVAS:
        # Remove o termo se ele estiver no texto
        texto = texto.replace(termo, " ")
        
    # 4. Limpeza final de pontuação e espaços extras
    texto = re.sub(r'[^\w\s]', ' ', texto) # Remove pontuação restante
    texto = re.sub(r'\s+', ' ', texto).strip() # Remove espaços duplos
    
    return texto

def limpar_texto_basico(texto):
    """Função leve usada apenas para limpeza simples (busca BM25/Keywords)."""
    if not texto: return ""
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

# =============================================================================
# 3. MÓDULO DE COLETA (Lógica do coletor_camara.py)
# =============================================================================
def salvar_json(dados, nome_arquivo, data=None):
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            if data:
                f.write(f"{data}\n")
            json.dump(dados, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[ERRO] Falha ao salvar {nome_arquivo}: {e}")

def carregar_json(nome_arquivo):
    if not os.path.exists(nome_arquivo): return None
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            f.readline()
            return json.load(f)

    except: return None
def ler_data_json(nome_arquivo):
    if not os.path.exists(nome_arquivo): return None
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            return f.readline().strip()
    except: return None

def obter_lista_ids(session, base_url, dt_inicio, dt_fim, tipos):
    proposicoes = []
    curr = dt_inicio
    print(f"\n[COLETA] Buscando IDs de {dt_inicio.date()} até {dt_fim.date()}...", flush=True)

    while curr < dt_fim:
        next_date = curr + timedelta(days=60) # Blocos de 60 dias para evitar timeout
        if next_date > dt_fim: next_date = dt_fim
        
        dt_ini_str = curr.strftime("%Y-%m-%d")
        dt_fim_str = next_date.strftime("%Y-%m-%d")
        
        url = f"{base_url}/proposicoes"
        params = {
            "dataApresentacaoInicio": dt_ini_str,
            "dataApresentacaoFim": dt_fim_str,
            "siglaTipo": ",".join(tipos),
            "itens": 100, "ordem": "ASC", "ordenarPor": "id"
        }
        
        while url:
            try:
                r = session.get(url, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                proposicoes.extend(data.get('dados', []))
                
                next_link = next((l['href'] for l in data.get('links', []) if l['rel'] == 'next'), None)
                url = next_link
                params = None 
            except Exception as e:
                print(f"    Erro na paginação: {e}")
                break
        curr = next_date + timedelta(days=1)
    
    # Remove duplicatas
    unicos = {p['id']: p for p in proposicoes}.values()
    return list(unicos)

def executar_coleta_completa():
    ids_salvos = carregar_json(NOME_ARQUIVO_CACHE_IDS)
    session = requests.Session()
    # 1. Obter IDs (se não existir cache ou se quiser forçar atualização)
    if not ids_salvos:
        ids_salvos = obter_lista_ids(session, CAMARA_BASE_URL, DATA_INICIO_COLETA, DATA_FIM_COLETA, TIPOS_DOCUMENTO)
        salvar_json(ids_salvos, NOME_ARQUIVO_CACHE_IDS)
    else:
        print(f"[CACHE] Usando lista de IDs existente: {len(ids_salvos)} itens.", flush=True)

    # 2. Obter Detalhes + Cache Partidário
    cache_partidos = {}
    proposicoes_detalhadas = []
    total = len(ids_salvos)
    
    print("\n[COLETA] Obtendo detalhes das proposições...", flush=True)
    for i, item in enumerate(ids_salvos):
        prop_id = item['id']
        
        if (i + 1) % 50 == 0: 
            print(f" -> Progresso: {i + 1}/{total}", flush=True)

        try:
            r = session.get(f"{CAMARA_BASE_URL}/proposicoes/{prop_id}", timeout=10)
            if r.status_code != 200: continue
            
            dados = r.json().get('dados', {})
            
            # URL Oficial
            dados['url_pagina_web_oficial'] = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={dados.get('id')}"

            # Tratamento de Autores
            uri_autores = dados.get('uriAutores')
            autor_nome = "Desconhecido"
            autor_partido = "S/P"
            coautores = []

            if uri_autores:
                try:
                    r_aut = session.get(uri_autores, timeout=5)
                    lista_autores = r_aut.json().get('dados', [])
                    
                    if lista_autores:
                        principal = lista_autores[0]
                        autor_nome = principal.get('nome')
                        uri_deputado = principal.get('uri')

                        # Cache de Partido
                        if uri_deputado:
                            if uri_deputado in cache_partidos:
                                autor_partido = cache_partidos[uri_deputado]
                            else:
                                try:
                                    r_dep = session.get(uri_deputado, timeout=5)
                                    d_dep = r_dep.json().get('dados', {})
                                    autor_partido = d_dep.get('ultimoStatus', {}).get('siglaPartido', 'S/P')
                                    cache_partidos[uri_deputado] = autor_partido
                                except:
                                    pass 
                        
                        if len(lista_autores) > 1:
                            coautores = [a.get('nome') for a in lista_autores[1:]]
                except:
                    pass 

            dados['autor_principal_nome'] = autor_nome
            dados['autor_principal_partido'] = autor_partido
            dados['coautores_nomes'] = coautores
            proposicoes_detalhadas.append(dados)

        except Exception as e:
            print(f"Erro ID {prop_id}: {e}")
            session.close()
            session = requests.Session()
            time.sleep(1)

    session.close()
    salvar_json(proposicoes_detalhadas, NOME_ARQUIVO_BANCO_DADOS, DATA_INICIO_COLETA)
    return proposicoes_detalhadas


# =============================================================================
# 4. MÓDULO DE KEYWORDS (Lógica do gerador_keywords.py)
# =============================================================================
def gerar_keywords_embeddings(db_dados, model):
    print("\n[KEYWORDS] Gerando embeddings das palavras-chave...", flush=True)
    
    # Palavras que aparecem no campo 'keywords' da Câmara mas não ajudam
    BLACKLIST = {"projeto", "lei", "sobre", "alteracao", "criacao", "instituicao", "federal", "nacional"}
    unique_keywords = set()
    
    for projeto in db_dados:
        texto = projeto.get('keywords') or projeto.get('indexacao')
        if texto:
            termos = texto.replace(';', ',').split(',')
            for termo in termos:
                # Usa a função de limpeza simples para keywords
                t_limpo = limpar_texto_basico(termo).upper()
                if len(t_limpo) > 3 and t_limpo.lower() not in BLACKLIST:
                    unique_keywords.add(t_limpo)
    
    lista_keywords = sorted(list(unique_keywords))
    
    # Vetorização
    embeddings = model.encode(lista_keywords, batch_size=64, show_progress_bar=True, convert_to_tensor=True)
    
    dados_pkl = {"keywords_texto": lista_keywords, "keywords_vectors": embeddings.cpu()}
    with open(NOME_ARQUIVO_PKL, "wb") as f:
        pickle.dump(dados_pkl, f)
    
    return dados_pkl

# =============================================================================
# 5. MÓDULO FILTRADOR (Lógica do filtrador_v3_final.py)
# =============================================================================
def extrair_metadados_para_csv(p):
    # Tratamento de Autores
    autor_principal = p.get('autor_principal_nome')
    coautores = p.get('coautores_nomes')
    
    lista_autores = []
    if autor_principal: lista_autores.append(str(autor_principal))
    if coautores:
        if isinstance(coautores, list): lista_autores.extend([str(c) for c in coautores])
        elif isinstance(coautores, str): lista_autores.append(coautores)
    
    autores_finais = list(dict.fromkeys(lista_autores)) # Remove duplicatas

    # Tratamento de Status
    status = p.get('statusProposicao')
    ultimo_estado = ""
    data_ultimo = ""
    situacao = ""
    
    if isinstance(status, dict):
        ultimo_estado = status.get('descricaoTramitacao', '') or status.get('despacho', '')
        data_ultimo = status.get('dataHora', '') or status.get('data', '')
        situacao = status.get('descricaoSituacao', '')

    return {
        "autores": ", ".join(autores_finais) if autores_finais else "Não informado",
        "partido": p.get('autor_principal_partido', ''),
        "ultimo_estado": ultimo_estado,
        "data_ultimo": data_ultimo,
        "situacao": situacao
    }

def executar_filtragem(db, kw_data, model):
    print(f"\n[FILTRO] Iniciando busca híbrida: '{CONSULTA_USUARIO}'", flush=True)
    
    # A) Prepara Embeddings das Ementas (Cache)
    if os.path.exists(ARQUIVO_CACHE_EMB) and os.path.getsize(ARQUIVO_CACHE_EMB) > 0:
        try:
            embs_ementas = np.load(ARQUIVO_CACHE_EMB)
            # Verifica se o tamanho do cache bate com o DB atual
            if len(embs_ementas) != len(db): 
                raise ValueError("Tamanho do cache diferente do DB")
            print(" -> Cache de ementas carregado.", flush=True)
        except:
            print(" -> Gerando embeddings das ementas (Atualizando)...", flush=True)
            textos = [limpar_ementa_para_vetorizacao(p.get('ementa', '')) for p in db]
            embs_ementas = model.encode(textos, batch_size=32, show_progress_bar=True)
            np.save(ARQUIVO_CACHE_EMB, embs_ementas)
    else:
        print(" -> Gerando embeddings das ementas (Primeira vez)...", flush=True)
        textos = [limpar_ementa_para_vetorizacao(p.get('ementa', '')) for p in db]
        embs_ementas = model.encode(textos, batch_size=32, show_progress_bar=True)
        np.save(ARQUIVO_CACHE_EMB, embs_ementas)

    # B) Prepara Embeddings da Query e Keywords Boost
    emb_query = model.encode(limpar_ementa_para_vetorizacao(CONSULTA_USUARIO), convert_to_tensor=True)
    scores_kw = util.cos_sim(emb_query, kw_data['keywords_vectors'])[0]
    top_kw = torch.topk(scores_kw, k=30)
    
    tags_alvo = []
    for sc, idx in zip(top_kw.values, top_kw.indices):
        if float(sc) > 0.65:
            tags_alvo.append(kw_data['keywords_texto'][idx])

    print(f" -> Tags de Boost identificadas: {tags_alvo[:5]}...", flush=True)

    # C) Cálculo de Similaridade
    sim_scores = util.cos_sim(emb_query, embs_ementas)[0].numpy()
    resultados = []

    for i, p in enumerate(db):
        score_sem = float(sim_scores[i])
        score_boost = 0.0
        
        # Boost se tiver tag relevante
        raw_tags = (p.get('keywords') or '') + ' ' + (p.get('indexacao') or '')
        # Limpeza simples para comparar com tags
        p_tags_upper = limpar_texto_basico(raw_tags).upper()
        
        for tag in tags_alvo:
            if tag in p_tags_upper:
                score_boost = 1.0
                break
        
        final_score = (score_sem * PESO_SEMANTICO) + (score_boost * PESO_KEYWORD)
        
        if final_score >= FILTRO_THRESHOLD:
            meta = extrair_metadados_para_csv(p)
            
            # Formatação para o CSV
            resultados.append({
                "Norma": f"{p.get('siglaTipo')} {p.get('numero')}/{p.get('ano')}",
                "Similaridade Semantica": f"{final_score:.4f}",
                "Descricao da Sigla": p.get('descricaoTipo', p.get('siglaTipo', '')),
                "Data de Apresentacao": p.get('dataApresentacao', '')[:10],
                "Autor": meta['autores'],
                "Partido": meta['partido'],
                "Ementa": p.get('ementa', '').strip(),
                "Link Documento PDF": p.get('urlInteiroTeor', ''),
                "Link Página Web": p.get('url_pagina_web_oficial', ''),
                "Indexacao": p.get('keywords', p.get('indexacao', '')),
                "Último Estado": meta['ultimo_estado'],
                "Data Último Estado": meta['data_ultimo'][:10],
                "Situação": meta['situacao']
            })

    # D) Salvar CSV
    if resultados:
        colunas = list(resultados[0].keys())
        # IMPORTANTE: Delimitador vírgula para compatibilidade com insert_data.py
        with open(NOME_ARQUIVO_SAIDA_FINAL_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=colunas, delimiter=',') 
            writer.writeheader()
            writer.writerows(resultados)
        print(f"\n[SUCESSO] Arquivo '{NOME_ARQUIVO_SAIDA_FINAL_CSV}' gerado com {len(resultados)} linhas.", flush=True)
    else:
        print("\n[AVISO] Nenhum resultado encontrado com os filtros atuais.", flush=True)

# =============================================================================
# 6. ORQUESTRAÇÃO PRINCIPAL (MAIN)
# =============================================================================
if __name__ == "__main__":
    print("--- INICIANDO SISTEMA UNIFICADO DE COLETA E FILTRAGEM (OASIS) ---", flush=True)

    data = ler_data_json(NOME_ARQUIVO_BANCO_DADOS)
    if data:
        cache_data = datetime.strptime((data), "%Y-%m-%d %H:%M:%S")
    else:
        cache_data = None

    # 1. Carrega ou Coleta Dados
    db_dados = carregar_json(NOME_ARQUIVO_BANCO_DADOS)
    if not db_dados:
        db_dados = executar_coleta_completa()
    elif DATA_INICIO_COLETA != cache_data:
        os.remove(NOME_ARQUIVO_BANCO_DADOS)
        os.remove(NOME_ARQUIVO_CACHE_IDS)
        if (os.path.exists("projetos_em_csv\proposicoes_camara_resumo.csv")):
            os.remove("projetos_em_csv\proposicoes_camara_resumo.csv")
        db_dados = executar_coleta_completa()
    else:
        print(f"[DB] Base de dados carregada: {len(db_dados)} registros.", flush=True)

    # 2. Prepara Modelo
    print(f"\n[MODELO] Carregando {MODELO_NOME}...", flush=True)
    model = SentenceTransformer(MODELO_NOME)

    # 3. Gera ou Carrega Keywords
    kw_data = None
    if os.path.exists(NOME_ARQUIVO_PKL):
        try:
            with open(NOME_ARQUIVO_PKL, 'rb') as f: kw_data = pickle.load(f)
        except: pass
    
    if not kw_data:
        kw_data = gerar_keywords_embeddings(db_dados, model)

    # 4. Filtra e Exporta CSV
    executar_filtragem(db_dados, kw_data, model)
    
    print("\n--- PROCESSO FINALIZADO ---", flush=True)