"""
Módulo de Extração de Dados (ETL) da API da Câmara dos Deputados.

Responsável por:
- Consultar a API de Dados Abertos para buscar projetos de lei (PL, PLP, PEC).
- Realizar paginação e gerenciar limites de requisição (Rate Limit 429).
- Executar extração em paralelo (Multithreading) para acelerar o download.
- Particionar os dados salvos em arquivos JSON por legislatura (Sharding).
- Sincronizar de forma incremental, baixando apenas projetos novos desde a última execução.
"""
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

import gzip


CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
TIPOS_DOCUMENTO = ["PL", "PLP", "PEC"]

# Aponta para a nova pasta de dados estruturada
ARQUIVO_CACHE_PARTIDOS = os.path.join(config.PASTA_DADOS, "cache_partidos.json")

# --- NOVO: Arquivo que vai guardar a memória da última execução ---
ARQUIVO_METADADOS = os.path.join(config.PASTA_DADOS, "metadata_coleta.json")

MAX_WORKERS = 10 

# Variáveis para segurança no uso de múltiplas threads
thread_local = threading.local()
cache_lock = threading.Lock()

def get_session():
    """
    Garante que cada Thread tenha sua própria sessão HTTP isolada.
    
    Reutilizar sessões HTTP (connection pooling) acelera as requisições, 
    mas requests.Session() não é 'thread-safe' por padrão. Essa função 
    evita conflitos de conexão entre as threads concorrentes.

    Returns:
        requests.Session: Sessão HTTP vinculada à thread atual.
    """
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

def obter_lista_ids(base_url, data_inicio_global, data_fim_global, tipos):
    """
    Varre a API da Câmara para coletar os IDs de todas as proposições em um período.

    Faz a paginação automática saltando de 90 em 90 dias (para não sobrecarregar
    a API com buscas muito longas de uma vez).

    Args:
        base_url (str): URL base da API da Câmara.
        data_inicio_global (datetime): Data de início da busca.
        data_fim_global (datetime): Data de término da busca.
        tipos (list): Lista de siglas de projetos (ex: ["PL", "PEC"]).

    Returns:
        list: Lista contendo os IDs únicos (inteiros) encontrados no período.
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
                # Lida com o erro 429 (Too Many Requests) da API
                if r.status_code == 429:
                    time.sleep(5)
                    continue
                r.raise_for_status()
                dados = r.json()

                for p in dados.get('dados', []): ids_encontrados.add(p['id'])

                links = dados.get('links', [])
                url = next((link['href'] for link in links if link['rel'] == 'next'), None)
                params = None # Limpa params porque a próxima URL já vem completa
            except Exception:
                break
        data_atual = data_proxima + timedelta(days=1)
    session.close()
    return list(ids_encontrados)

def processar_uma_proposicao(prop_id, cache_autores):
    """
    Busca os metadados detalhados de um único projeto de lei.

    Esta função é chamada concorrentemente pelas Threads. Ela busca a ementa, 
    autor principal, partido e coautores. Utiliza um cache de partidos em 
    memória para evitar bater na API de Deputados repetidas vezes.

    Args:
        prop_id (int): O ID numérico da proposição.
        cache_autores (dict): Dicionário em memória mapeando URI de deputado para partido.

    Returns:
        dict ou None: O dicionário com os dados completos do projeto, ou None em caso de falha.
    """
    session = get_session()
    url_detalhe = f"{CAMARA_BASE_URL}/proposicoes/{prop_id}"

    # Tenta até 3 vezes (Retry mechanism) em caso de instabilidade de rede
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
                            # Utiliza LOCK para leitura/escrita segura no cache compartilhado entre as threads
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
    Orquestrador Multithread para download e separação (Sharding) dos projetos.

    Distribui os IDs encontrados para um Pool de Threads (trabalhadores independentes).
    Conforme os projetos são baixados, agrupa-os em categorias (legislaturas)
    para evitar arquivos muito pesados.

    Args:
        lista_ids (list): Lista com milhares de IDs de projetos.

    Returns:
        dict: Dicionário onde a chave é a legislatura (ex: 'leg57') e o valor
              é a lista de dicionários com os projetos completos.
    """
    print(f"\nExtração MULTITHREAD de {len(lista_ids)} projetos...", flush = True)

    cache_autores = {}
    if os.path.exists(ARQUIVO_CACHE_PARTIDOS):
        with open(ARQUIVO_CACHE_PARTIDOS, 'r', encoding='utf-8') as f: cache_autores = json.load(f)

    bancos_separados = {}
    total, processados, start_time = len(lista_ids), 0, time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Envia todas as tarefas para a fila das threads
        futuros = {executor.submit(processar_uma_proposicao, pid, cache_autores): pid for pid in lista_ids}

        # Conforme as threads terminam, processa os resultados
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

def atualizar_historico_tramitacoes():
    """
    Baixa o histórico de tramitações (andamentos) para TODOS os projetos locais.
    
    Varre os arquivos JSON de base gerados na coleta, extrai os IDs e faz uma
    varredura paralela pesada (15 workers) batendo no endpoint `/tramitacoes`.
    O resultado é compactado em GZIP (.gz) devido ao alto volume de texto.
    """
    print("🔄 Iniciando sincronização GLOBAL de históricos em arquivos JSON locais...")
    
    padrao_busca = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos_json = glob.glob(padrao_busca)
    
    projetos_para_atualizar = []
    ids_mapeados = set()
    
    for arquivo in arquivos_json:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                for p in dados:
                    id_oficial = p.get('id')
                    norma_string = f"{p.get('siglaTipo', '')} {p.get('numero', '')}/{p.get('ano', '')}".upper().strip()
                    if id_oficial and norma_string and id_oficial not in ids_mapeados:
                        ids_mapeados.add(id_oficial)
                        projetos_para_atualizar.append((id_oficial, norma_string))

    total_projetos = len(projetos_para_atualizar)
    if total_projetos == 0:
        print("⚠️ Nenhum projeto localizado nos arquivos JSON locais.")
        return

    arquivo_historico_json = os.path.join(config.PASTA_DADOS, "camara_tramitacoes_cache.json.gz")
    
    cache_historico_completo = {}
    if os.path.exists(arquivo_historico_json):
        with gzip.open(arquivo_historico_json, 'rt', encoding='utf-8') as f:
            try:
                cache_historico_completo = json.load(f)
            except:
                cache_historico_completo = {}

    print(f"🚀 Iniciando download PARALELO (Multithreading) de {total_projetos} históricos para o arquivo JSON GZIP...")

    def baixar_historico_json(id_camara, norma):
        url = f"https://dadosabertos.camara.leg.br/api/v2/proposicoes/{id_camara}/tramitacoes"
        try:
            resposta = requests.get(url, timeout=10)
            if resposta.status_code == 200:
                dados_api = resposta.json().get('dados', [])
                dados_ordenados = sorted(dados_api, key=lambda k: k.get('sequencia', 0), reverse=True)
                
                lista_tramitacoes_projeto = []
                for t in dados_ordenados:
                    lista_tramitacoes_projeto.append({
                        "data_tramitacao": t.get('dataHora', '')[:10] if t.get('dataHora') else None,
                        "sequencia": t.get('sequencia'),
                        "orgao": t.get('siglaOrgao', 'Plenário'),
                        "descricao_tramitacao": t.get('descricaoTramitacao', 'Sem descrição'),
                        "situacao_tramitacao": t.get('descricaoSituacao', 'Não informada'),
                        "apreciacao": t.get('apreciacao', 'Não informada'),
                        "despacho": t.get('despacho', 'Sem despacho registrado')
                    })
                return norma, lista_tramitacoes_projeto
        except Exception as e:
            print(f"⚠️ Falha na norma {norma} (ID: {id_camara}): {e}")
        return norma, None

    processados = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futuros = {executor.submit(baixar_historico_json, pid, item_norma): item_norma for pid, item_norma in projetos_para_atualizar}
        
        for futuro in concurrent.futures.as_completed(futuros):
            processados += 1
            norma_chave, resultado_tramitacoes = futuro.result()
            
            if resultado_tramitacoes is not None:
                cache_historico_completo[norma_chave] = resultado_tramitacoes
                
            if processados % 50 == 0 or processados == total_projetos:
                print(f"📶 Progresso Global: [{processados}/{total_projetos}] históricos em cache...", flush=True)

    with gzip.open(arquivo_historico_json, 'wt', encoding='utf-8') as f:
        json.dump(cache_historico_completo, f, indent=4, ensure_ascii=False)

    print("✅ Base de dados de históricos completamente populada e congelada em JSON!")

# ==========================================================
# FUNÇÃO DE EXECUÇÃO EXPORTÁVEL (Para uso no Streamlit)
# ==========================================================
def executar_coleta_incremental():
    """
    Encapsula a lógica de Smart Sync para ser chamada externamente.
    
    Função principal exportável (entry point para o Streamlit/main.py).

    Implementa a lógica de 'Smart Sync' (Sincronização Incremental).
    Lê o arquivo de metadados para descobrir quando foi a última coleta,
    e busca apenas os projetos criados de lá para cá, fundindo-os com a base atual.
    Também dispara a sincronização dos andamentos no final.
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

    # NOVO: Dispara a população automática do histórico
    try:
        atualizar_historico_tramitacoes()
    except Exception as e:
        print(f"⚠️ Alerta: Não foi possível sincronizar o histórico de andamentos: {e}")


# ==========================================================
# BLOCO DE EXECUÇÃO DIRETA
# ==========================================================
if __name__ == "__main__":
    executar_coleta_incremental()