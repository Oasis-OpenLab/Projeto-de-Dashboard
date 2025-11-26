import subprocess
import os
import shutil
import mysql.connector
import sys

# --- CONFIGURAÇÃO DO BANCO DE DADOS (PARA RODAR O ARQUIVO .SQL) ---
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "dudu2004"  

def executar_api():
    print("\n>>> [1/4] Coletando dados da API (acess_api.py)...")
    # Roda a coleta
    subprocess.run([sys.executable, "acess_api.py"], check=True)
    
    # CORREÇÃO DE CAMINHO:
    # O api salva na raiz, mas o insert procura na pasta 'projetos_em_csv'
    arquivo_gerado = "proposicoes_camara_resumo.csv"
    pasta_destino = "projetos_em_csv"
    
    if os.path.exists(arquivo_gerado):
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino)
            print(f"Pasta '{pasta_destino}' criada.")
            
        destino_final = os.path.join(pasta_destino, arquivo_gerado)
        # Move e substitui se já existir
        shutil.move(arquivo_gerado, destino_final)
        print(f"Arquivo CSV movido para: {destino_final}")
    else:
        print("AVISO: O arquivo CSV não foi gerado pela API.")

def recriar_banco():
    print("\n>>> [2/4] Recriando Banco de Dados (create_database.sql)...")
    
    # Lendo o arquivo SQL
    if not os.path.exists("create_database.sql"):
        print("Erro: create_database.sql não encontrado.")
        return

    with open("create_database.sql", "r", encoding="utf-8") as f:
        sql_script = f.read()

    # Conectando ao MySQL
    try:
        cnx = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = cnx.cursor()
        
        commands = sql_script.split(';')
        
        for command in commands:
            # Pula comandos vazios (ex: linhas em branco no final do arquivo)
            if command.strip():
                try:
                    cursor.execute(command)
                except mysql.connector.Error as err:
                    # Ignora erros de "Drop database" se ela não existir
                    if err.errno == 1008: 
                        pass
                    else:
                        print(f"Erro ao executar comando SQL: {err}")
                        raise err
            
        cnx.commit()
        cursor.close()
        cnx.close()
        print("Banco de dados 'Oasis' recriado com sucesso.")
    except mysql.connector.Error as err:
        print(f"Erro crítico no banco: {err}")
        print("DICA: Verifique se a senha no main.py está igual à do seu MySQL.")
        sys.exit(1)

def inserir_dados():
    print("\n>>> [3/4] Inserindo dados no SQL (insert_data.py)...")
    try:
        subprocess.run([sys.executable, "insert_data.py"], check=True)
    except subprocess.CalledProcessError:
        print("Erro ao inserir dados. Verifique se a senha no arquivo 'insert_data.py' está correta.")
        sys.exit(1)

def abrir_dashboard():
    print("\n>>> [4/4] Iniciando Dashboard (Streamlit)...")
    print("Pressione Ctrl+C no terminal para encerrar o servidor.")
    # Streamlit roda com um comando diferente do Python normal
    subprocess.run(["streamlit", "run", "dashboard.py"], check=True)

if __name__ == "__main__":
    print("--- INICIANDO PIPELINE DE DADOS OASIS ---")
    
    # 1. Coleta e Organiza Arquivos
    executar_api()
    
    # 2. Prepara o Banco (Reset)
    recriar_banco()
    
    # 3. Popula o Banco
    inserir_dados()
    
    # 4. Visualiza
    abrir_dashboard()