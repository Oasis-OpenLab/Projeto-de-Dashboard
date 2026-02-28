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

    Por que isso existe?
    - requests.Session() reaproveita conexões TCP (connection pooling).
    - Criar uma nova sessão a cada requisição é custoso.
    - Como estamos usando múltiplas threads, não é seguro compartilhar
      uma única Session global entre elas.

    Solução adotada:
    - Cada thread possui sua própria sessão (thread-local storage).
    - Isso evita conflitos e melhora performance.

    thread_local é um objeto especial onde cada thread tem seu
    próprio espaço de atributos.
    """
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session

def obter_lista_ids(base_url, data_inicio_global, data_fim_global, tipos):
    """
    Objetivo:
        Buscar TODOS os IDs de proposições no intervalo de datas especificado,
        filtrando pelos tipos desejados (PL, PLP, PEC, etc).

    Estratégia:
    1) Divide o intervalo total em blocos menores de 90 dias.
       Isso evita:
           - Respostas muito grandes
           - Timeout
           - Problemas de paginação excessiva
    2) Para cada bloco de datas:
           - Faz requisição paginada à API
           - Coleta apenas os IDs (não detalhes completos)
           - Armazena em um set para evitar duplicatas
    3) Retorna lista final de IDs únicos.

    Essa função NÃO busca detalhes.
    Ela apenas constrói a lista base para o processamento posterior.
    """
    print(f"A procurar IDs (Período: {data_inicio_global.strftime('%d/%m/%Y')} até {data_fim_global.strftime('%d/%m/%Y')})...")
    
    # Usamos set para evitar duplicatas automaticamente.
    ids_encontrados = set()
    
    # Sessão simples (não precisa ser thread-local aqui,
    # pois essa função roda de forma sequencial).
    session = requests.Session()
    
    # Dividimos em blocos de 90 dias para controlar volume.
    passo_dias = timedelta(days=90) 
    data_atual = data_inicio_global

    # Percorre o intervalo de datas
    while data_atual <= data_fim_global:
        data_proxima = min(data_atual + passo_dias, data_fim_global)
        print(f"-> A varrer período: {data_atual.strftime('%Y-%m-%d')} até {data_proxima.strftime('%Y-%m-%d')}")
        
        url = f"{base_url}/proposicoes"

        # Parâmetros da API:
        # - dataApresentacaoInicio/Fim: filtro por data
        # - siglaTipo: tipos de proposição
        # - itens=100: máximo por página
        # - ordenação crescente por ID (estável para paginação)
        params = {
            "dataApresentacaoInicio": data_atual.strftime("%Y-%m-%d"), 
            "dataApresentacaoFim": data_proxima.strftime("%Y-%m-%d"), 
            "siglaTipo": tipos, 
            "itens": 100, 
            "ordem": "ASC", 
            "ordenarPor": "id"
        }

        # Loop de paginação
        while url:
            try:
                r = session.get(url, params=params, timeout=15)
                # Se API sinalizar rate limit (429), aguardamos e tentamos novamente.
                if r.status_code == 429:
                    time.sleep(5)
                    continue
                r.raise_for_status()
                dados = r.json()

                # Coleta apenas os IDs
                for p in dados.get('dados', []): ids_encontrados.add(p['id'])

                # Verifica se há link para próxima página
                links = dados.get('links', [])
                url = next((link['href'] for link in links if link['rel'] == 'next'), None)

                # Após primeira página, params já estão embutidos na URL.
                params = None
            except Exception as e:
                # Se houver erro, abandona esse bloco de datas.
                break
        # Avança para o próximo intervalo de 90 dias
        data_atual = data_proxima + timedelta(days=1)
    session.close()
    return list(ids_encontrados)

def processar_uma_proposicao(prop_id, cache_autores):
    """
    Objetivo:
        Buscar detalhes completos de uma proposição e enriquecê-la com:
            - URL pública oficial
            - Autor principal
            - Partido do autor principal
            - Lista de coautores

    Entrada:
        - prop_id: ID da proposição
        - cache_autores: dict compartilhado entre threads que mapeia { uri_deputado: sigla_partido }

    Retorno:
        - dict com dados completos enriquecidos
        - ou None se falhar
    """
    # Obtém sessão específica da thread
    session = get_session()
    url_detalhe = f"{CAMARA_BASE_URL}/proposicoes/{prop_id}"

    # Tentamos até 3 vezes em caso de erro
    for _ in range(3):
        try:
            # Pega a resposta da requisicao de proposição detalhada da API
            r = session.get(url_detalhe, timeout=10)

            # Tratamento de rate limit
            if r.status_code == 429:
                time.sleep(2)
                continue
            if r.status_code != 200: return None

            # Extrai dados principais
            dados = r.json().get('dados', {})

            # Monta URL oficial pública da proposição
            uri_str = dados.get('uri', '')
            dados['url_pagina_web_oficial'] = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={uri_str.rstrip('/').split('/')[-1]}" if uri_str else ""

            # Valores padrão
            autor_nome, autor_partido, coautores = "Desconhecido", "N/A", []
            uri_autores = dados.get('uriAutores')

            if uri_autores:
                r_aut = session.get(uri_autores, timeout=10)
                if r_aut.status_code == 200:
                    lista_autores = r_aut.json().get('dados', [])
                    if lista_autores:
                        # Primeiro autor é considerado principal
                        autor_principal = lista_autores[0]
                        autor_nome = autor_principal.get('nome', 'Desconhecido')
                        uri_deputado = autor_principal.get('uri')

                        # Só buscamos partido se for deputado
                        if uri_deputado and 'deputados' in uri_deputado:
                            # Verifica no cache com lock
                            with cache_lock: tem_no_cache = uri_deputado in cache_autores
                            if tem_no_cache: autor_partido = cache_autores[uri_deputado]
                            else:
                                # Busca detalhes do deputado
                                r_dep = session.get(uri_deputado, timeout=10)
                                if r_dep.status_code == 200:
                                    autor_partido = r_dep.json().get('dados', {}).get('ultimoStatus', {}).get('siglaPartido', 'N/A')
                                    # Atualiza cache com lock
                                    with cache_lock: cache_autores[uri_deputado] = autor_partido
                        # Demais autores viram coautores
                        if len(lista_autores) > 1: coautores = [a.get('nome') for a in lista_autores[1:]]

            # Enriquecimento final do objeto
            dados['autor_principal_nome'] = autor_nome
            dados['autor_principal_partido'] = autor_partido
            dados['coautores_nomes'] = coautores
            return dados
        # Em caso de erro inesperado, espera e tenta novamente
        except: time.sleep(1)
    return None

def obter_detalhes_e_separar(lista_ids):
    """
    FUNÇÃO PRINCIPAL DE EXTRAÇÃO E PARTICIONAMENTO.

    Responsabilidades:
    1) Processar cada ID de proposição em paralelo (multithread).
    2) Enriquecer cada proposição (via processar_uma_proposicao).
    3) Separar os resultados por legislatura (sharding lógico).
    4) Retornar os dados para que a função main faça o Merge Incremental.
    """
    print(f"\nExtração MULTITHREAD de {len(lista_ids)} projetos...")

    # Cache em memória que armazena: { uri_deputado: sigla_partido }
    cache_autores = {}
    if os.path.exists(ARQUIVO_CACHE_PARTIDOS):
        with open(ARQUIVO_CACHE_PARTIDOS, 'r', encoding='utf-8') as f: cache_autores = json.load(f)

    # Estrutura final onde vamos armazenar os projetos organizados por legislatura
    bancos_separados = {}
    total, processados, start_time = len(lista_ids), 0, time.time()

    # Criamos um pool de threads para processar múltiplas proposições simultaneamente.
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(processar_uma_proposicao, pid, cache_autores): pid for pid in lista_ids}

        for futuro in concurrent.futures.as_completed(futuros):
            processados += 1
            res = futuro.result()
            if res:
                # Determina a legislatura a partir do ano da proposição.
                leg = obter_legislatura(res.get('ano', 0))
                if leg not in bancos_separados: bancos_separados[leg] = []
                # Adicionamos o projeto enriquecido na lista correspondente à sua legislatura.
                bancos_separados[leg].append(res)

            # A cada 100 projetos (ou no final), exibimos métricas de desempenho.
            if processados % 100 == 0 or processados == total:
                vel = processados / (time.time() - start_time)
                eta = (total - processados) / vel / 60 if vel > 0 else 0
                print(f"[{processados}/{total}] Vel: {vel:.1f} p/s | ETA: {eta:.1f} min")

    # Após finalizar todas as threads, salvamos o cache atualizado de partidos em disco.
    with open(ARQUIVO_CACHE_PARTIDOS, 'w', encoding='utf-8') as f: json.dump(cache_autores, f, ensure_ascii=False)

    # --- NOVO: Retorna o dicionário de legislaturas para a função principal gerenciar ---
    return bancos_separados

if __name__ == "__main__":
    """
    BLOCO DE EXECUÇÃO PRINCIPAL DO SCRIPT.

    Responsabilidades atualizadas (Smart Sync):
        1) Garantir que a pasta de dados exista.
        2) Ler o metadata_coleta.json para descobrir quando foi a última execução.
        3) Buscar apenas as proposições criadas APÓS a última execução.
        4) Fazer o MERGE (mescla) dos dados novos com os dados antigos já existentes.
        5) Atualizar o metadata.json para o dia de hoje.
    """

    # Garante que a pasta onde os arquivos JSON serão salvos exista.
    if not os.path.exists(config.PASTA_DADOS): os.makedirs(config.PASTA_DADOS)

    hoje = datetime.now()
    data_inicio_busca = config.DATA_INICIO_COLETA

    # --- NOVO: LÓGICA DE ATUALIZAÇÃO INCREMENTAL ---
    # Verifica se já rodamos esse código antes
    if os.path.exists(ARQUIVO_METADADOS):
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta = json.load(f)
            if "ultima_coleta" in meta:
                # Transforma a data salva em formato de texto para formato Data
                ultima_data = datetime.strptime(meta["ultima_coleta"], "%Y-%m-%d")
                data_inicio_busca = ultima_data
                print(f"\n[CACHE] Sincronização Incremental: Buscando apenas dados novos desde {ultima_data.strftime('%d/%m/%Y')}.")
    else:
        print(f"\n[CACHE] Primeira execução. Iniciando coleta completa a partir de {data_inicio_busca.strftime('%d/%m/%Y')}.")

    # 1) Busca todos os IDs de proposições dentro do intervalo ajustado (completo ou incremental)
    ids = obter_lista_ids(CAMARA_BASE_URL, data_inicio_busca, hoje, TIPOS_DOCUMENTO)
    
    # 2) Se houver IDs encontrados, executa extração detalhada e particionamento.
    if ids: 
        novos_dados_separados = obter_detalhes_e_separar(ids)
        
        # --- NOVO: LÓGICA DE MESCLA (MERGE) DOS JSONs ---
        for leg, projetos_novos in novos_dados_separados.items():
            nome_arquivo = os.path.join(config.PASTA_DADOS, f"camara_db_{leg}.json")
            dados_existentes = []

            # Se a "gaveta" JSON da legislatura já existe, nós a abrimos
            if os.path.exists(nome_arquivo):
                with open(nome_arquivo, 'r', encoding='utf-8') as f:
                    dados_existentes = json.load(f)

            # Extrai os IDs de todos os projetos que já temos para não duplicar dados
            ids_existentes = {p['id'] for p in dados_existentes}
            # Filtra e deixa passar apenas os projetos que o ID não está na lista dos existentes
            projetos_unicos = [p for p in projetos_novos if p['id'] not in ids_existentes]

            # Se depois de filtrar sobrou algo novo, nós adicionamos no final da lista
            if projetos_unicos:
                dados_existentes.extend(projetos_unicos)
                # Salva o JSON atualizado
                with open(nome_arquivo, 'w', encoding='utf-8') as f:
                    json.dump(dados_existentes, f, indent=4, ensure_ascii=False)
                print(f"-> Atualizado: {nome_arquivo} (+{len(projetos_unicos)} novos. Total: {len(dados_existentes)})")
            else:
                print(f"-> Nenhum projeto novo para adicionar em {leg}.")
    else:
        print("-> Nenhum projeto novo encontrado no período.")

    # --- NOVO: Atualiza a memória do sistema para o dia de hoje ---
    with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
        json.dump({"ultima_coleta": hoje.strftime("%Y-%m-%d")}, f)