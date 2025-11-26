import mysql.connector
import csv
import datetime

cnx = mysql.connector.connect(user='root', password='dudu2004', host='localhost', database='Oasis')
cursor = cnx.cursor()

# Mapeia Nomes do CSV (Chave) para Nomes do Banco (Valor)
column_map = {
    "Norma": "norma",
    "Descricao da Sigla": "descricao",
    'Data de Apresentacao': 'datadeapresentacao',
    "Autor": "autor",
    "Partido": "partido",
    "Ementa": "ementa",
    "Link Documento PDF": "linkpdf",
    "Link Página Web": "linkweb",
    "Indexacao": "indexacao",
    "Último Estado": "ultimoestado",
    "Data Último Estado": "dataultimo",
    "Situação": "situacao"
}

csv_file_path = './projetos_em_csv/proposicoes_camara_resumo.csv'

with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    header = next(reader) # Contém os nomes originais do CSV

    # Remove a coluna 'Similaridade Semantica'
    if 'Similaridade Semantica' in header:
        index_to_remove = header.index('Similaridade Semantica')
        header.pop(index_to_remove)
    else:
        index_to_remove = None

    # Mapeia os nomes do CSV para os nomes do banco
    # A variável 'header' (original) ainda será usada para encontrar os índices
    mapped_columns = [column_map.get(col, col) for col in header]

    columns = ','.join([f"`{col}`" for col in mapped_columns])
    placeholders = ','.join(['%s'] * len(mapped_columns))
    sql = f"INSERT INTO Projetos ({columns}) VALUES ({placeholders})"

    
    # Índice para 'Data de Apresentacao'
    try:
        date_index_apresentacao = header.index('Data de Apresentacao')
    except ValueError:
        print("Aviso: Coluna 'Data de Apresentacao' não encontrada.")
        date_index_apresentacao = -1

    # Índice para 'Data Último Estado'
    try:
        date_index_ultimo = header.index('Data Último Estado')
    except ValueError:
        print("Aviso: Coluna 'Data Último Estado' não encontrada.")
        date_index_ultimo = -1

    for row in reader:
        if index_to_remove is not None:
            row.pop(index_to_remove)  # remove o valor da coluna

        values = [None if val == '' else val for val in row]
        
        # Converte a 'Data de Apresentacao'
        if date_index_apresentacao != -1 and values[date_index_apresentacao]:
            try:
                parsed_date = datetime.datetime.strptime(values[date_index_apresentacao], '%Y-%m-%d')
                values[date_index_apresentacao] = parsed_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                values[date_index_apresentacao] = None

        # Converte a 'Data Último Estado'
        if date_index_ultimo != -1 and values[date_index_ultimo]:
            try:
                parsed_date = datetime.datetime.strptime(values[date_index_ultimo], '%Y-%m-%d')
                values[date_index_ultimo] = parsed_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                values[date_index_ultimo] = None
        
        try:
            cursor.execute(sql, values)
        except mysql.connector.errors.IntegrityError:
            pass

cnx.commit()
cursor.close()
cnx.close()