"""
File name: insert_data.py
Brief: Le dados do csv e implementa em uma tabela no banco de dados

"""
import mysql.connector
import csv
import datetime
import os
import sys
import config

#Configurações de Usuário no Programa MySQL
cnx = mysql.connector.connect(user=config.USUARIO, password=config.SENHA, host=config.HOST, database=config.NOME, port = config.porta, ssl_ca = config.certificado)
cursor = cnx.cursor()

# Mapeia Nomes do CSV (Chave) para Nomes do Banco (Valor)
column_map = {
    "Norma": "norma", "Descricao da Sigla": "descricao", 'Data de Apresentacao': 'datadeapresentacao',
    "Autor": "autor", "Partido": "partido", "Ementa": "ementa", "Link Documento PDF": "linkpdf",
    "Link Página Web": "linkweb", "Indexacao": "indexacao", "Último Estado": "ultimoestado",
    "Data Último Estado": "dataultimo", "Situação": "situacao", 
    "Score Final": "score_relevancia" # <--- ADICIONADO AQUI
}

csv_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projetos_em_csv', 'proposicoes_camara_resumo.csv')  #Caminho do arquivo

#Abre o arquivo csv em modo de leitura
with open(csv_file_path, mode='r', encoding='utf-8-sig') as csvfile:
    reader = csv.reader(csvfile, delimiter=';') #Objeto de Leitura
    header = next(reader) #Lista dos nomes originais

    # Remove a coluna 'Similaridade Semantica'
    colunas_ignoradas = ['Boost Keyword', 'Similaridade Semantica', 'raw_score']
    indices_remover = sorted([header.index(col) for col in colunas_ignoradas if col in header], reverse=True)
    for idx in indices_remover: header.pop(idx)

    # Índice para 'Data de Apresentacao' e 'Data Último Estado'
    date_index_apr = header.index('Data de Apresentacao') if 'Data de Apresentacao' in header else -1
    date_index_ult = header.index('Data Último Estado') if 'Data Último Estado' in header else -1

    for row in reader:
        for idx in indices_remover: row.pop(idx)  #remove das linhas o valor da coluna similaridade
        values = [None if val == '' else val for val in row]

        # Converte a 'Data de Apresentacao' para formato yyyy-mm-dd usado pelo MySQL
        if date_index_apr != -1 and values[date_index_apr]:
            try: values[date_index_apr] = datetime.datetime.strptime(values[date_index_apr], '%Y-%m-%d').strftime('%Y-%m-%d')
            except: pass
        
        # Converte a 'Data Último Estado' para formato yyyy-mm-dd usado pelo MySQL
        if date_index_ult != -1 and values[date_index_ult]:
            try: values[date_index_ult] = datetime.datetime.strptime(values[date_index_ult], '%Y-%m-%d').strftime('%Y-%m-%d')
            except: pass

        #Tenta inserir os dados no Banco MySQL linha a linha
        db_columns = [column_map[col] for col in header]
        insert_query = f"INSERT INTO Projetos ({', '.join(db_columns)}) VALUES ({', '.join(['%s'] * len(values))})"
        try: cursor.execute(insert_query, values)
        except: pass

    #Finalização do Código
    cnx.commit()
    cursor.close()
    cnx.close()
    print("Dados inseridos no banco MySQL com sucesso!")