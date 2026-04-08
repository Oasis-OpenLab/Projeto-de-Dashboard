import requests
import json
import os
import time
import glob
from datetime import datetime, timedelta
import threading
import concurrent.futures
import config
from utils_legislativo import obter_legislatura

CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
TIPOS_DOCUMENTO = ["PL", "PLP", "PEC"]

# Aponta para a nova pasta de dados estruturada
ARQUIVO_CACHE_PARTIDOS = os.path.join(config.PASTA_DADOS, "cache_partidos.json")

# --- NOVO: Arquivo que vai guardar a memória da última execução ---
ARQUIVO_METADADOS = os.path.join(config.PASTA_DADOS, "metadata_coleta.json")

MAX_WORKERS = 10 
thread_local = threading.local()
cache_lock = threading.Lock()

def get_session():
    """
    Retorna uma sessão HTTP específica da thread atual.
    """
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

def obter_lista_ids(base_url, data_inicio_global, data_fim_global, tipos):
    """
    Objetivo: Buscar TODOS os IDs de proposições no intervalo de datas especificado.
    """
    print(f"A procurar IDs (Período: {data_inicio_global.strftime('%d/%m/%Y')} até {data_fim_global.strftime('%d/%m/%Y')})...", flush=True)
    
    ids_encontrados = set()
    session = requests.Session()
    passo_dias = timedelta(days=90) 
    data_atual = data_inicio_global

    while data_atual <= data_fim_global:
        data_proxima = min(data_atual + passo_dias, data_fim_global)
        print(f"-> A varrer período: {data_atual.strftime('%Y-%m-%d')} até {data_proxima.strftime('%Y-%m-%d')}", flush = True)
        
        url = f"{base_url}/proposicoes"
        params = {
            "dataApresentacaoInicio": data_atual.strftime("%Y-%m-%d"), 
            "dataApresentacaoFim": data_proxima.strftime("%Y-%m-%d"), 
            "siglaTipo": tipos, 
            "itens": 100, 
            "ordem": "ASC", 
            "ordenarPor": "id"
        }

        while url:
            try:
                r = session.get(url, params=params, timeout=15)
                if r.status_code == 429:
                    time.sleep(5)
                    continue
                r.raise_for_status()
                dados = r.json()

                for p in dados.get('dados', []): ids_encontrados.add(p['id'])

                links = dados.get('links', [])
                url = next((link['href'] for link in links if link['rel'] == 'next'), None)
                params = None
            except Exception:
                break
        data_atual = data_proxima + timedelta(days=1)
    session.close()
    return list(ids_encontrados)

def processar_uma_proposicao(prop_id, cache_autores):
    """
    Objetivo: Buscar detalhes completos de uma proposição e enriquecê-la.
    """
    session = get_session()
    url_detalhe = f"{CAMARA_BASE_URL}/proposicoes/{prop_id}"

    for _ in range(3):
        try:
            r = session.get(url_detalhe, timeout=10)
            if r.status_code == 429:
                time.sleep(2)
                continue
            if r.status_code != 200: return None

            dados = r.json().get('dados', {})
            uri_str = dados.get('uri', '')
            dados['url_pagina_web_oficial'] = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={uri_str.rstrip('/').split('/')[-1]}" if uri_str else ""

            autor_nome, autor_partido, coautores = "Desconhecido", "N/A", []
            uri_autores = dados.get('uriAutores')

            if uri_autores:
                r_aut = session.get(uri_autores, timeout=10)
                if r_aut.status_code == 200:
                    lista_autores = r_aut.json().get('dados', [])
                    if lista_autores:
                        autor_principal = lista_autores[0]
                        autor_nome = autor_principal.get('nome', 'Desconhecido')
                        uri_deputado = autor_principal.get('uri')

                        if uri_deputado and 'deputados' in uri_deputado:
                            with cache_lock: tem_no_cache = uri_deputado in cache_autores
                            if tem_no_cache: autor_partido = cache_autores[uri_deputado]
                            else:
                                r_dep = session.get(uri_deputado, timeout=10)
                                if r_dep.status_code == 200:
                                    autor_partido = r_dep.json().get('dados', {}).get('ultimoStatus', {}).get('siglaPartido', 'N/A')
                                    with cache_lock: cache_autores[uri_deputado] = autor_partido
                        
                        if len(lista_autores) > 1: coautores = [a.get('nome') for a in lista_autores[1:]]

            dados['autor_principal_nome'] = autor_nome
            dados['autor_principal_partido'] = autor_partido
            dados['coautores_nomes'] = coautores
            return dados
        except: time.sleep(1)
    return None

def obter_detalhes_e_separar(lista_ids):
    """
    FUNÇÃO PRINCIPAL DE EXTRAÇÃO E PARTICIONAMENTO.
    """
    print(f"\nExtração MULTITHREAD de {len(lista_ids)} projetos...", flush = True)

    cache_autores = {}
    if os.path.exists(ARQUIVO_CACHE_PARTIDOS):
        with open(ARQUIVO_CACHE_PARTIDOS, 'r', encoding='utf-8') as f: cache_autores = json.load(f)

    bancos_separados = {}
    total, processados, start_time = len(lista_ids), 0, time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(processar_uma_proposicao, pid, cache_autores): pid for pid in lista_ids}

        for futuro in concurrent.futures.as_completed(futuros):
            processados += 1
            res = futuro.result()
            if res:
                leg = obter_legislatura(res.get('ano', 0))
                if leg not in bancos_separados: bancos_separados[leg] = []
                bancos_separados[leg].append(res)

            if processados % 100 == 0 or processados == total:
                vel = processados / (time.time() - start_time)
                eta = (total - processados) / vel / 60 if vel > 0 else 0
                print(f"[{processados}/{total}] Vel: {vel:.1f} p/s | ETA: {eta:.1f} min", flush = True)

    with open(ARQUIVO_CACHE_PARTIDOS, 'w', encoding='utf-8') as f: json.dump(cache_autores, f, ensure_ascii=False)
    return bancos_separados

# ==========================================================
# FUNÇÃO DE EXECUÇÃO EXPORTÁVEL (Para uso no Streamlit)
# ==========================================================
def executar_coleta_incremental():
    """
    Encapsula a lógica de Smart Sync para ser chamada externamente.
    """
    if not os.path.exists(config.PASTA_DADOS): os.makedirs(config.PASTA_DADOS)

    hoje = datetime.now()
    data_inicio_busca = config.DATA_INICIO_COLETA

    if os.path.exists(ARQUIVO_METADADOS):
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta = json.load(f)
            if "ultima_coleta" in meta:
                ultima_data = datetime.strptime(meta["ultima_coleta"], "%Y-%m-%d")
                data_inicio_busca = ultima_data
                print(f"\n[CACHE] Sincronização Incremental: Buscando dados novos desde {ultima_data.strftime('%d/%m/%Y')}.", flush = True)
    else:
        print(f"\n[CACHE] Primeira execução. Coleta completa a partir de {data_inicio_busca.strftime('%d/%m/%Y')}.")

    ids = obter_lista_ids(CAMARA_BASE_URL, data_inicio_busca, hoje, TIPOS_DOCUMENTO)
    
    if ids: 
        novos_dados_separados = obter_detalhes_e_separar(ids)
        
        for leg, projetos_novos in novos_dados_separados.items():
            nome_arquivo = os.path.join(config.PASTA_DADOS, f"camara_db_{leg}.json")
            dados_existentes = []

            if os.path.exists(nome_arquivo):
                with open(nome_arquivo, 'r', encoding='utf-8') as f:
                    dados_existentes = json.load(f)

            ids_existentes = {p['id'] for p in dados_existentes}
            projetos_unicos = [p for p in projetos_novos if p['id'] not in ids_existentes]

            if projetos_unicos:
                dados_existentes.extend(projetos_unicos)
                with open(nome_arquivo, 'w', encoding='utf-8') as f:
                    json.dump(dados_existentes, f, indent=4, ensure_ascii=False)
                print(f"-> Atualizado: {nome_arquivo} (+{len(projetos_unicos)} novos).")
            else:
                print(f"-> Nenhum projeto novo para {leg}.")
    else:
        print("-> Nenhum projeto novo encontrado no período.", flush = True)

    with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
        json.dump({"ultima_coleta": hoje.strftime("%Y-%m-%d")}, f)

# ==========================================================
# BLOCO DE EXECUÇÃO DIRETA
# ==========================================================
if __name__ == "__main__":
    executar_coleta_incremental()