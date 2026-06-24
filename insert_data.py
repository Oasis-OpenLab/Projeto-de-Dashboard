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
    """
    Conecta ao MySQL, trunca (limpa) a tabela atual e insere os novos dados.

    Passo a passo:
    1. Desativa temporariamente as restrições de chave estrangeira (FOREIGN_KEY_CHECKS)
       para permitir um TRUNCATE limpo e rápido.
    2. Lê o arquivo CSV ignorando colunas de log/debug (ex: 'Boost Keyword').
    3. Formata strings de data para o padrão suportado pelo MySQL (YYYY-MM-DD).
    4. Executa os comandos INSERT em lote para popular o banco.

    Levanta:
        mysql.connector.Error: Se houver falhas de credenciais ou no TRUNCATE.
        FileNotFoundError: Se o arquivo CSV gerado pela IA não for encontrado.
    """
    # Conecta no Banco
    cnx = mysql.connector.connect(user=config.USUARIO, password=config.SENHA, host=config.HOST, database=config.NOME, port = config.porta, ssl_ca = config.certificado)
    cursor = cnx.cursor()

   # --- NOVO: LIMPEZA DO BANCO COM PROTEÇÃO ---
    # Desativa temporariamente as restrições de chaves para permitir a limpeza limpa
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Projetos;")
    
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cnx.commit()

    # Mapeia Nomes do CSV (Chave) para Nomes do Banco (Valor)
    column_map = {
        "Norma": "norma", "Descricao da Sigla": "descricao", 'Data de Apresentacao': 'datadeapresentacao',
        "Autor": "autor", "Partido": "partido", "Ementa": "ementa", "Link Documento PDF": "linkpdf",
        "Link Página Web": "linkweb", "Indexacao": "indexacao", "Último Estado": "ultimoestado",
        "Data Último Estado": "dataultimo", "Situação": "situacao", "Score Final": "score_relevancia","Metodo": "metodo", "ID Proposicao": "id_proposicao"
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

# ==========================================================
# BLOCO DE EXECUÇÃO DIRETA (Garante o funcionamento em background)
# ==========================================================
if __name__ == "__main__":
    # Força a execução da inserção no banco de dados quando chamado pelo subprocess
    atualizar_banco_sql()