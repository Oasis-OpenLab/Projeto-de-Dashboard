
#sem limite de proposições para a tabela e pontuação acima de 0.5

import requests
import json
import os
import time
import re
import csv
from datetime import datetime, timedelta

# --- Novas importações necessárias para a busca semântica ---
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer, util
# -----------------------------------------------------------

# --- Funções de Utilidade Compartilhadas ---
def salvar_para_json(dados, nome_arquivo):
    """
    Salva um dicionário/lista Python em um arquivo JSON.
    """
    try:
        with open(nome_arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)
        print(f"\nDados salvos com sucesso em '{nome_arquivo}'")
        print(f"O arquivo '{nome_arquivo}' foi criado no diretório: {os.getcwd()}")
    except IOError as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao salvar o arquivo: {e}")

def remover_acentos(texto):
    """
    Remove acentos de uma string para facilitar a comparação.
    """
    if not isinstance(texto, str):
        return texto
    texto = re.sub(r'[ÁÀÂÃÄ]', 'A', texto)
    texto = re.sub(r'[ÉÈÊË]', 'E', texto)
    texto = re.sub(r'[ÍÌÎÏ]', 'I', texto)
    texto = re.sub(r'[ÓÒÔÕÖ]', 'O', texto)
    texto = re.sub(r'[ÚÙÛÜ]', 'U', texto)
    texto = re.sub(r'[Ç]', 'C', texto)
    texto = re.sub(r'[áàâãä]', 'a', texto)
    texto = re.sub(r'[éèêë]', 'e', texto)
    texto = re.sub(r'[íìîï]', 'i', texto)
    texto = re.sub(r'[óòôõö]', 'o', texto)
    texto = re.sub(r'[úùûü]', 'u', texto)
    texto = re.sub(r'[ç]', 'c', texto)
    return texto

# --- Funções de Busca e Filtro para a Câmara ---

# --- FUNÇÃO DE FILTRO SEMÂNTICO (Modificada para retornar score) ---
def filtrar_proposicoes_por_semantica(lista_proposicoes, consulta, coluna_texto="ementa",
                                      top_k=20, modelo="all-MiniLM-L6-v2", threshold=None):
    """
    Filtra proposições com base na similaridade semântica da ementa em relação à consulta.
    Retorna uma lista de dicionários [{'id': <id>, 'score': <similaridade>}]
    """

    if not lista_proposicoes or not isinstance(lista_proposicoes, list):
        print("Nenhuma proposição válida recebida.")
        return []

    # 1. Cria DataFrame
    df = pd.DataFrame(lista_proposicoes)

    if coluna_texto not in df.columns:
        print(f"Aviso: Coluna '{coluna_texto}' não encontrada em todas as proposições. Usando valores nulos.")
        if coluna_texto not in df.columns:
            df[coluna_texto] = ""

    textos = df[coluna_texto].fillna("").astype(str).tolist()

    # 2. Gera embeddings
    print(f"\nGerando embeddings para {len(textos)} textos...")
    model = SentenceTransformer(modelo)
    emb_textos = model.encode(textos, batch_size=32, show_progress_bar=True)

    # 3. Calcula similaridade da query com todas as ementas
    print(f"Calculando similaridade com a consulta: '{consulta}'")
    emb_query = model.encode(consulta, convert_to_tensor=True)
    sims = util.cos_sim(emb_query, emb_textos)[0].cpu().numpy()

    # 4. Seleciona (aplica threshold primeiro, depois top_k se houver)
    indices_ordenados = np.argsort(-sims)
    
    indices_filtrados = indices_ordenados
    if threshold is not None:
        indices_filtrados = [i for i in indices_ordenados if sims[i] >= threshold]
        print(f"Encontrados {len(indices_filtrados)} resultados acima do threshold ({threshold}).")
    else:
        print(f"Nenhum threshold aplicado.")

    # Aplica o limite top_k (se top_k não for None)
    if top_k is not None:
        indices_finais = indices_filtrados[:top_k]
        print(f"Selecionando TOP {top_k} (ou menos, se filtrado pelo threshold).")
    else:
        indices_finais = indices_filtrados # <--- MUDANÇA: Usa todos os filtrados se top_k for None
        print(f"Sem limite de TOP K. Selecionando todos os {len(indices_finais)} resultados acima do threshold.")


    # 5. Pega IDs e SCORES correspondentes
    if "id" not in df.columns:
        raise ValueError("Erro crítico: Campo 'id' não encontrado nas proposições.")

    # --- MUDANÇA AQUI: Retorna dict com ID e Score ---
    resultados_filtrados = []
    for i in indices_finais:
        resultados_filtrados.append({
            'id': df.iloc[i]["id"],
            'score': float(sims[i]) # Adiciona o score de similaridade
        })

    # Debug opcional
    print("\nProposições mais próximas (TOP 5 da lista final):")
    for i in indices_finais[:5]:
        ementa_preview = df.iloc[i][coluna_texto]
        if ementa_preview:
            ementa_preview = ementa_preview[:80] + "..."
        else:
            ementa_preview = "[Ementa Vazia]"
        print(f"- ID: {df.iloc[i]['id']} | Sim: {sims[i]:.3f} | Ementa: {ementa_preview}")

    print(f"\nTotal de proposições filtradas: {len(resultados_filtrados)}")
    return resultados_filtrados
    # --- FIM DA MUDANÇA NA FUNÇÃO ---


def obter_proposicoes_camara_por_data(base_url, data_inicio_apresentacao=None, data_fim_apresentacao=None, siglas_tipo=None, atraso_entre_paginas=0.1):
    """
    Obtém proposições da API da Câmara dos Deputados... (função sem alteração)
    """
    proposicoes = []
    url_inicial = f"{base_url}/proposicoes"
    
    current_params = {
        "itens": 100,
        "ordem": "ASC",
        "ordenarPor": "id"
    } 
    
    if data_inicio_apresentacao:
        current_params["dataApresentacaoInicio"] = data_inicio_apresentacao
    if data_fim_apresentacao:
        current_params["dataApresentacaoFim"] = data_fim_apresentacao
    
    if siglas_tipo and isinstance(siglas_tipo, list):
        current_params["siglaTipo"] = ",".join(siglas_tipo)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    current_url = url_inicial
    
    print(f"Buscando lista de proposições da Câmara com filtros: {current_params}")
    
    while current_url:
        for attempt in range(3):
            try:
                response = requests.get(current_url, params=current_params if current_url == url_inicial else None, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if 'dados' in data and isinstance(data['dados'], list):
                    proposicoes.extend(data['dados'])
                else:
                    print("Estrutura da resposta da API da Câmara para proposições inesperada ou lista vazia.")
                    current_url = None
                    break
                
                next_link = None
                for link in data.get('links', []):
                    if link.get('rel') == 'next':
                        next_link = link.get('href')
                        break
                
                current_url = next_link
                
                if next_link:
                    paginas_coletadas = len(proposicoes) // current_params.get('itens', 1) if current_params.get('itens', 0) > 0 else 0
                    print(f"  Página {paginas_coletadas + 1} de proposições coletada. Total até agora: {len(proposicoes)}")
                    time.sleep(atraso_entre_paginas)
                
                break
            
            except requests.exceptions.RequestException as e:
                print(f"  Erro na requisição (Tentativa {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)
                else:
                    print(f"    Falha após 3 tentativas. Parando a coleta para esta data.")
                    current_url = None 
                    break 
            except json.JSONDecodeError:
                print("  Erro ao decodificar JSON da lista de proposições da Câmara. Parando a coleta.")
                current_url = None
                break
            except Exception as e:
                print(f"  Ocorreu um erro inesperado: {e}. Parando a coleta.")
                current_url = None
                break
            
    print(f"Total final de proposições básicas encontradas no período: {len(proposicoes)}")
    return proposicoes


def buscar_detalhes_proposicoes_camara_por_ids(ids_list, base_url, atraso_entre_requisicoes=0.1):
    proposicoes_detalhadas = []
    total_ids = len(ids_list)
    print(f"\nBuscando detalhes para {total_ids} proposições filtradas (por semântica)...")
    for i, id_proposicao in enumerate(ids_list):
        url_detalhes = f"{base_url}/proposicoes/{id_proposicao}"
        print(f"  Buscando detalhes para ID {id_proposicao} ({i + 1}/{total_ids})...")
        for attempt in range(3):
            try:
                response = requests.get(url_detalhes)
                response.raise_for_status()
                data = response.json()
                if 'dados' in data:
                    proposicao_detalhada = data['dados']
                    uri_autores = proposicao_detalhada.get('uriAutores')
                    if uri_autores:
                        nomes_autores_lista = []
                        autores_detalhes_lista = []
                        try:
                            autores_response = requests.get(uri_autores)
                            autores_response.raise_for_status()
                            autores_data_json = autores_response.json()
                            if 'dados' in autores_data_json and isinstance(autores_data_json['dados'], list):
                                for autor in autores_data_json['dados']:
                                    autor_nome = autor.get('nome')
                                    autor_uri_deputado = autor.get('uri')
                                    autor_partido = 'Não Informado'
                                    if autor_nome and autor_uri_deputado:
                                        try:
                                            deputado_response = requests.get(autor_uri_deputado)
                                            deputado_response.raise_for_status()
                                            deputado_data_json = deputado_response.json()
                                            partido = deputado_data_json.get('dados', {}).get('ultimoStatus', {}).get('siglaPartido')
                                            if partido:
                                                autor_partido = partido
                                        except requests.exceptions.RequestException:
                                            pass
                                    nomes_autores_lista.append(autor_nome)
                                    autores_detalhes_lista.append({'nome': autor_nome, 'partido': autor_partido})
                                    time.sleep(atraso_entre_requisicoes)
                            proposicao_detalhada['autoresCompletos'] = nomes_autores_lista
                            proposicao_detalhada['autoresDetalhes'] = autores_detalhes_lista
                        except requests.exceptions.RequestException as e:
                            print(f"    Erro ao buscar autores para proposição {id_proposicao}: {e}")
                        time.sleep(atraso_entre_requisicoes) 
                    proposicoes_detalhadas.append(proposicao_detalhada)
                break
            except requests.exceptions.RequestException as e:
                print(f"  Erro na requisição de detalhes (Tentativa {attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)
                else:
                    print(f"    Falha após 3 tentativas. Pulando para a próxima proposição.")
                    break 
    print(f"Total de proposições detalhadas coletadas: {len(proposicoes_detalhadas)}")
    return proposicoes_detalhadas

def transform_camara_data_to_summary(raw_camara_json):
    if not isinstance(raw_camara_json, dict) or not raw_camara_json: return None
    id_proposicao = raw_camara_json.get('id')
    sigla_tipo = raw_camara_json.get('siglaTipo')
    numero = raw_camara_json.get('numero')
    ano = raw_camara_json.get('ano')
    ementa = raw_camara_json.get('ementa', '').strip()
    url_inteiro_teor = raw_camara_json.get('urlInteiroTeor')
    url_pagina_web = raw_camara_json.get('uri')
    autores_detalhes_list = raw_camara_json.get('autoresDetalhes', [])
    autor_principal_nome, autor_principal_partido = ('', '')
    if autores_detalhes_list:
        primeiro_autor = autores_detalhes_list[0]
        autor_principal_nome = primeiro_autor.get('nome', '')
        autor_principal_partido = primeiro_autor.get('partido', '')
    resumo_autoria_str = "; ".join([a['nome'] for a in autores_detalhes_list if a.get('nome')])
    indexacao_data = raw_camara_json.get('keywords', '')
    status_proposicao = raw_camara_json.get('statusProposicao', {})
    descricao_tramitacao_status = status_proposicao.get('descricaoTramitacao', 'Não Informado')
    data_hora_status_tramitacao = status_proposicao.get('dataHora', None) 
    descricao_situacao = status_proposicao.get('descricaoSituacao', 'Não Informado')
    return {"id": id_proposicao, "codigoMateria": id_proposicao, "identificacao": f"{sigla_tipo} {numero}/{ano}" if all([sigla_tipo, numero, ano]) else id_proposicao, "sigla": sigla_tipo, "descricaoSigla": raw_camara_json.get('descricaoTipo', "N/I"), "numero": numero, "ano": ano, "casaIdentificadora": "Camara dos Deputados", "siglaEnteIdentificador": "CD", "identificacaoExterna": {}, "conteudo": {"id": id_proposicao, "idTipo": raw_camara_json.get('codTipo'), "siglaTipo": sigla_tipo, "tipo": raw_camara_json.get('descricaoTipo'), "ementa": ementa}, "documento": {"id": id_proposicao, "siglaTipo": sigla_tipo, "tipo": raw_camara_json.get('descricaoTipo'), "dataApresentacao": raw_camara_json.get('dataApresentacao'), "indexacao": indexacao_data, "url": url_inteiro_teor, "autoria": autores_detalhes_list, "resumoAutoria": resumo_autoria_str, "autorPrincipal": autor_principal_nome, "partidoAutorPrincipal": autor_principal_partido}, "tramitando": descricao_tramitacao_status, "dataHoraStatusTramitacao": data_hora_status_tramitacao, "descricaoSituacao": descricao_situacao, "urlPaginaWeb": url_pagina_web, "classificacoes": [], "autoriaIniciativa": []}

def salvar_para_csv(dados_json, nome_arquivo):
    # --- MUDANÇA AQUI: Adicionada "Similaridade Semantica" ---
    colunas_mapeamento = {
        "Norma": "identificacao", 
        "Descricao da Sigla": "descricaoSigla", 
        "Data de Apresentacao": "documento.dataApresentacao", 
        "Autor": "documento.autorPrincipal", 
        "Partido": "documento.partidoAutorPrincipal", 
        "Ementa": "conteudo.ementa", 
        "Similaridade Semantica": "similaridade", # <--- NOVA COLUNA
        "Link Documento PDF": "documento.url", 
        "Link Página Web": "urlPaginaWeb", 
        "Indexacao": "documento.indexacao", 
        "Último Estado": "tramitando", 
        "Data Último Estado": "dataHoraStatusTramitacao", 
        "Situação": "descricaoSituacao"
    }
    # --- FIM DA MUDANÇA ---

    fieldnames = list(colunas_mapeamento.keys())
    try:
        with open(nome_arquivo, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for item in dados_json:
                row = {}
                for csv_col, json_path in colunas_mapeamento.items():
                    value = item
                    for part in json_path.split('.'):
                        if isinstance(value, dict): value = value.get(part, None)
                        else: value = None; break
                    if ("Data" in csv_col) and value and isinstance(value, str):
                        value = value.split('T')[0]
                    # Formata o score para 3 casas decimais se for a coluna de similaridade
                    if csv_col == "Similaridade Semantica" and isinstance(value, float):
                         value = f"{value:.3f}"
                    row[csv_col] = str(value) if value is not None else ''
                writer.writerow(row)
        print(f"\nDados salvos com sucesso em '{nome_arquivo}'")
    except IOError as e: print(f"Erro ao salvar o arquivo CSV: {e}")


#------------------ A PARTIR DAQUI É POSSÍVEL FAZER ALTERAÇÕES ----------------------------------

# --- Configurações e Execução Principal ---      
CAMARA_BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"

# --- PARÂMETROS DE FILTRO ATUALIZADOS ---
CONSULTA_SEMANTICA_CAMARA = "Projetos de lei sobre inteligência artificial e internet"
FILTRO_TOP_K = None                 # <--- MUDANÇA: None = Sem limite, pega todos acima do threshold
FILTRO_THRESHOLD = 0.45             # <--- MUDANÇA: Filtra por 50% de similaridade
# --------------------------------------

TIPOS_DOCUMENTO_SIGLAS = ["PL", "PLP", "PEC"]
NOME_ARQUIVO_SAIDA_FINAL_FORMATADO_JSON_CAMARA = "proposicoes_camara_final_formatado.json" 
NOME_ARQUIVO_SAIDA_FINAL_CSV_CAMARA = "proposicoes_camara_resumo.csv"
NOME_ARQUIVO_PROPOSICOES_BASICAS_BRUTAS_JSON_CAMARA = "proposicoes_camara_basicas_brutas.json" 
NOME_ARQUIVO_PROPOSICOES_DETALHADAS_BRUTAS_JSON_CAMARA = "proposicoes_camara_detalhadas_brutas.json"

if __name__ == "__main__":
    print("--- INICIANDO COLETA DE DADOS DA CÂMARA DOS DEPUTADOS ---")

    data_inicio_geral = datetime(2021, 1, 1)  #DATA DE APRESENTAÇÃO
    data_fim_limite = datetime(2021, 12, 1)

#------------------ A PARTIR DAQUI NÃO É MAIS POSSÍVEL FAZER ALTERAÇÕES ------------------------

    all_proposicoes_basicas_coletadas = []
    
    current_start_date = data_inicio_geral
    while current_start_date < data_fim_limite:
        # Calcula o fim do período (3 meses à frente)
        month = current_start_date.month + 3
        year = current_start_date.year
        if month > 12:
            month -= 12
            year += 1
        
        # O fim do período é um dia antes do início do próximo período de 3 meses
        end_of_period = datetime(year, month, 1) - timedelta(days=1)
        
        # Garante que o fim do período não ultrapasse o limite total
        if end_of_period > data_fim_limite:
            end_of_period = data_fim_limite

        data_inicio_str = current_start_date.strftime("%Y-%m-%d")
        data_fim_str = end_of_period.strftime("%Y-%m-%d")

        print(f"\n--- Coletando dados para o período: {data_inicio_str} a {data_fim_str} ---")
        
        proposicoes_do_periodo = obter_proposicoes_camara_por_data(
            CAMARA_BASE_URL,
            data_inicio_apresentacao=data_inicio_str,
            data_fim_apresentacao=data_fim_str,
            siglas_tipo=TIPOS_DOCUMENTO_SIGLAS
        )
        
        if proposicoes_do_periodo:
            all_proposicoes_basicas_coletadas.extend(proposicoes_do_periodo)
            print(f"Total acumulado de proposições básicas coletadas: {len(all_proposicoes_basicas_coletadas)}")
        else:
            print(f"Nenhuma proposição encontrada no período.")
        
        # Define o início do próximo período
        current_start_date = end_of_period + timedelta(days=1)
        time.sleep(1) 

    print(f"\n--- Coleta de todas as proposições básicas concluída. Total: {len(all_proposicoes_basicas_coletadas)} ---")

    if all_proposicoes_basicas_coletadas:
        salvar_para_json(all_proposicoes_basicas_coletadas, NOME_ARQUIVO_PROPOSICOES_BASICAS_BRUTAS_JSON_CAMARA)

        # --- CHAMADA DA FUNÇÃO ATUALIZADA ---
        # Agora recebe uma lista de dicts: [{'id': 1, 'score': 0.8}, ...]
        resultados_filtrados_semantica = filtrar_proposicoes_por_semantica( # <--- MUDANÇA
            lista_proposicoes=all_proposicoes_basicas_coletadas, 
            consulta=CONSULTA_SEMANTICA_CAMARA,
            coluna_texto="ementa", 
            top_k=FILTRO_TOP_K,
            threshold=FILTRO_THRESHOLD
        )
        # ------------------------------------
        
        if resultados_filtrados_semantica: # <--- MUDANÇA
            
            # <--- MUDANÇA: Criar mapa de scores e lista de IDs
            ids_para_buscar = [item['id'] for item in resultados_filtrados_semantica]
            mapa_scores = {item['id']: item['score'] for item in resultados_filtrados_semantica}
            # --- FIM DA MUDANÇA ---

            proposicoes_detalhadas_filtradas_ementa = buscar_detalhes_proposicoes_camara_por_ids(
                ids_para_buscar, CAMARA_BASE_URL # <--- MUDANÇA: Passa a lista de IDs extraída
            )
            
            if proposicoes_detalhadas_filtradas_ementa:
                salvar_para_json(proposicoes_detalhadas_filtradas_ementa, NOME_ARQUIVO_PROPOSICOES_DETALHADAS_BRUTAS_JSON_CAMARA)
                proposicoes_formatadas_camara = [transform_camara_data_to_summary(p) for p in proposicoes_detalhadas_filtradas_ementa if p]
                
                if proposicoes_formatadas_camara:
                    
                    # --- MUDANÇA: Adiciona o score em cada proposição formatada ---
                    print("Adicionando scores de similaridade aos dados formatados...")
                    for prop in proposicoes_formatadas_camara:
                        prop_id = prop.get('id')
                        if prop_id in mapa_scores:
                            prop['similaridade'] = mapa_scores[prop_id] # Adiciona o score
                        else:
                            prop['similaridade'] = None
                    # --- FIM DA MUDANÇA ---

                    print(f"\n--- Formatando {len(proposicoes_formatadas_camara)} proposições detalhadas ---")
                    salvar_para_json(proposicoes_formatadas_camara, NOME_ARQUIVO_SAIDA_FINAL_FORMATADO_JSON_CAMARA)
                    salvar_para_csv(proposicoes_formatadas_camara, NOME_ARQUIVO_SAIDA_FINAL_CSV_CAMARA)
                    print("\nScript de coleta da Câmara dos Deputados concluído com sucesso!")
                else:
                    print("Nenhuma proposição foi formatada com sucesso.")
            else:
                 print("Nenhuma proposição detalhada foi encontrada.")
        else:
            print("Nenhuma proposição encontrada com os critérios semânticos especificados.")
    else:
        print("Não foi possível obter a lista geral de proposições. Encerrando.")