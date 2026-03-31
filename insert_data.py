"""
File name: insert_data.py
Brief: Lê o CSV gerado pela IA e atualiza o banco de dados MySQL para o Dashboard ler.
"""
import mysql.connector
import csv
import datetime
import os
import config

def atualizar_banco_sql():
    """Conecta no MySQL, limpa a pesquisa anterior e insere os novos projetos filtrados."""
    # Conecta no Banco
    cnx = mysql.connector.connect(user=config.USUARIO, password=config.SENHA, host=config.HOST, database=config.NOME)
    cursor = cnx.cursor()

    # --- NOVO: LIMPEZA DO BANCO ---
    # Apaga os dados da pesquisa velha para não misturar assuntos no Dashboard
    cursor.execute("TRUNCATE TABLE Projetos")
    cnx.commit()

    # Mapeia Nomes do CSV (Chave) para Nomes do Banco (Valor)
    column_map = {
        "Norma": "norma", "Descricao da Sigla": "descricao", 'Data de Apresentacao': 'datadeapresentacao',
        "Autor": "autor", "Partido": "partido", "Ementa": "ementa", "Link Documento PDF": "linkpdf",
        "Link Página Web": "linkweb", "Indexacao": "indexacao", "Último Estado": "ultimoestado",
        "Data Último Estado": "dataultimo", "Situação": "situacao", "Score Final": "score_relevancia"
    }

    csv_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projetos_em_csv', 'proposicoes_camara_resumo.csv')

    with open(csv_file_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile, delimiter=';')
        header = next(reader) 

        # Ignora colunas técnicas de log
        colunas_ignoradas = ['Boost Keyword', 'Similaridade Semantica', 'raw_score']
        indices_remover = sorted([header.index(col) for col in colunas_ignoradas if col in header], reverse=True)
        for idx in indices_remover: header.pop(idx)

        date_index_apr = header.index('Data de Apresentacao') if 'Data de Apresentacao' in header else -1
        date_index_ult = header.index('Data Último Estado') if 'Data Último Estado' in header else -1

        for row in reader:
            for idx in indices_remover: row.pop(idx) 
            values = [None if val == '' else val for val in row]

            # Formata datas para o padrão do MySQL (YYYY-MM-DD)
            if date_index_apr != -1 and values[date_index_apr]:
                try: values[date_index_apr] = datetime.datetime.strptime(values[date_index_apr], '%Y-%m-%d').strftime('%Y-%m-%d')
                except: pass
            
            if date_index_ult != -1 and values[date_index_ult]:
                try: values[date_index_ult] = datetime.datetime.strptime(values[date_index_ult], '%Y-%m-%d').strftime('%Y-%m-%d')
                except: pass

            db_columns = [column_map[col] for col in header]
            insert_query = f"INSERT INTO Projetos ({', '.join(db_columns)}) VALUES ({', '.join(['%s'] * len(values))})"
            try: cursor.execute(insert_query, values)
            except: pass

    # Salva e fecha a conexão
    cnx.commit()
    cursor.close()
    cnx.close()
    print("Dados atualizados no banco MySQL com sucesso!")