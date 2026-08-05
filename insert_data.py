"""
Módulo de Ingestão de Dados (CSV -> MySQL).

Responsável por ler o arquivo CSV resultante do processo de filtragem 
híbrida e inserir os registros na tabela 'Projetos' do banco de dados 'Oasis'.
Também realiza a limpeza prévia da tabela de forma segura antes da inserção,
garantindo que o Dashboard reflita apenas a última pesquisa do usuário.
"""
import mysql.connector
import csv
import datetime
import os
import config

def atualizar_banco_sql():
    # Conecta no Banco
    cnx = mysql.connector.connect(user=config.USUARIO, password=config.SENHA, host=config.HOST, database=config.NOME, port = config.porta, ssl_ca = config.certificado)
    cursor = cnx.cursor()

    # --- LIMPEZA DO BANCO COM PROTEÇÃO ---
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Projetos;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cnx.commit()

    # Mapeia Nomes do CSV (Chave) para Nomes do Banco (Valor)
    column_map = {
        "ID Proposicao": "id_proposicao",
        "Norma": "norma", 
        "Descricao da Sigla": "descricao", 
        "Data de Apresentacao": "datadeapresentacao",
        "Autor": "autor", 
        "Partido": "partido", 
        "Ementa": "ementa", 
        "Link Documento PDF": "linkpdf",
        "Link Página Web": "linkweb", 
        "Indexacao": "indexacao", 
        "Último Estado": "ultimoestado",
        "Data Último Estado": "dataultimo", 
        "Situação": "situacao", 
        "Score Final": "score_relevancia",
        "Score Semantico (IA)": "score_semantico",
        "Score Politico (Tracao)": "score_politico",
        "Boost Keyword": "boost_keyword",
        "Metodo": "metodo"
    }

    csv_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projetos_em_csv', 'proposicoes_camara_resumo.csv')

    with open(csv_file_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        header = next(reader) 

        date_index_apr = header.index('Data de Apresentacao') if 'Data de Apresentacao' in header else -1
        date_index_ult = header.index('Data Último Estado') if 'Data Último Estado' in header else -1

        for row in reader:
            values = [None if val == '' else val for val in row]

            # Formata datas para o padrão do MySQL (YYYY-MM-DD)
            if date_index_apr != -1 and values[date_index_apr]:
                try: values[date_index_apr] = datetime.datetime.strptime(values[date_index_apr], '%Y-%m-%d').strftime('%Y-%m-%d')
                except: pass
            
            if date_index_ult != -1 and values[date_index_ult]:
                try: values[date_index_ult] = datetime.datetime.strptime(values[date_index_ult], '%Y-%m-%d').strftime('%Y-%m-%d')
                except: pass

            # Cria o comando SQL apenas com as colunas que realmente existem no CSV e no column_map
            db_columns = [column_map[col] for col in header if col in column_map]
            mapped_values = [values[i] for i, col in enumerate(header) if col in column_map]

            insert_query = f"INSERT INTO Projetos ({', '.join(db_columns)}) VALUES ({', '.join(['%s'] * len(mapped_values))})"
            try: 
                cursor.execute(insert_query, mapped_values)
            except Exception as e: 
                print(f"Aviso: Linha pulada devido a erro no SQL: {e}")

    # Salva e fecha a conexão
    cnx.commit()
    cursor.close()
    cnx.close()
    print("Dados atualizados no banco MySQL com sucesso!")

# ==========================================================
# BLOCO DE EXECUÇÃO DIRETA (Garante o funcionamento em background)
# ==========================================================
if __name__ == "__main__":
    atualizar_banco_sql()