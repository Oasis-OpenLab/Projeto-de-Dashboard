import subprocess
import os
import mysql.connector
import sys
import config

# --- CONFIGURAÇÃO GLOBAL DE CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def obter_caminho(nome_arquivo):
    """Retorna o caminho completo compatível com o sistema operacional"""
    return os.path.join(BASE_DIR, nome_arquivo)

def garantir_estrutura_pastas():
    """Verifica e cria as pastas necessárias para o projeto rodar"""
    print("\n>>> [0/4] Verificando estrutura de pastas...")
    
    pasta_csv = obter_caminho("projetos_em_csv")
    
    if not os.path.exists(pasta_csv):
        try:
            os.makedirs(pasta_csv)
            print(f"Pasta criada com sucesso: {pasta_csv}")
        except OSError as e:
            print(f"Erro ao criar pasta: {e}")
    else:
        print(f"Pasta já existe: {pasta_csv}")

def executar_api():
    print("\n>>> [1/4] Executando o Pipeline de IA (acess_api.py)...")
    script_path = obter_caminho("acess_api.py")
    try:
        subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
    except subprocess.CalledProcessError:
        print("[ERRO] Falha ao executar a coleta e filtragem de dados.")
        sys.exit(1)

def recriar_banco():
    print("\n>>> [2/4] Recriando banco de dados a partir do SQL (create_database.sql)...")
    sql_file = obter_caminho("create_database.sql")
    
    try:
        cnx = mysql.connector.connect(
            user=config.USUARIO,
            password=config.SENHA,
            host=config.HOST
        )
        cursor = cnx.cursor()
        
        with open(sql_file, 'r', encoding='utf-8') as file:
            sql_script = file.read()
            
        sql_commands = sql_script.split(';')
        
        for command in sql_commands:
            if command.strip():
                try:
                    cursor.execute(command)
                except mysql.connector.Error as err:
                    if err.errno == 1007: # Ignora erro de "banco já existe" se acontecer
                        pass
                    else:
                        print(f"Erro ao executar comando SQL: {err}")
                        raise err
                        
        cnx.commit()
        cursor.close()
        cnx.close()
        print("Banco de dados 'Oasis' recriado com sucesso.")
    except mysql.connector.Error as err:
        print(f"Erro crítico no banco: {err}. Verifique se o MySQL está rodando e a senha no config.py.")
        sys.exit(1)
    except Exception as e:
        print(f"Erro ao ler o arquivo SQL: {e}")
        sys.exit(1)

def inserir_dados():
    print("\n>>> [3/4] Inserindo dados filtrados no SQL (insert_data.py)...")
    script_path = obter_caminho("insert_data.py")
    try:
        subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
    except subprocess.CalledProcessError:
        print("Erro ao inserir dados. Verifique o arquivo insert_data.py.")
        sys.exit(1)

def abrir_dashboard():
    print("\n>>> [4/4] Iniciando Dashboard (Streamlit)...")
    print("---------------------------------------------------------")
    print("O navegador deve abrir automaticamente.")
    print("Para parar o servidor, pressione Ctrl+C neste terminal.")
    print("---------------------------------------------------------")
    
    dashboard_path = obter_caminho("dashboard.py")
    
    # Garante que estamos usando 'python.exe' para ver os logs no Windows
    executavel_python = sys.executable.replace("pythonw.exe", "python.exe")
    
    try:
        subprocess.run([executavel_python, "-m", "streamlit", "run", dashboard_path], check=True, cwd=BASE_DIR)
    except KeyboardInterrupt:
        print("\nServidor do Dashboard encerrado pelo usuário.")

def garantir_estrutura_pastas():
    print("\n>>> [0/4] Verificando estrutura de pastas...")
    pastas = [config.PASTA_DADOS, config.PASTA_CSV]
    
    for pasta in pastas:
        if not os.path.exists(pasta):
            os.makedirs(pasta)
            print(f"Pasta criada: {pasta}")
        else:
            print(f"Pasta pronta: {pasta}")

if __name__ == "__main__":
    try:
        print(f"--- INICIANDO PROJETO OASIS COMPLETO ---")
        print(f"Diretório base: {BASE_DIR}")
        
        # 0. Garante que as pastas existam
        garantir_estrutura_pastas()
        
        # 1. Coleta, Vetoriza e Filtra (Pipeline Híbrido)
        executar_api()
        
        # 2. Reseta as Tabelas do Banco
        recriar_banco()
        
        # 3. Insere o CSV Limpo no Banco
        inserir_dados()
        
        # 4. Sobe a Interface Web
        abrir_dashboard()
        
    except Exception as e:
        print(f"Ocorreu um erro fatal na execução principal: {e}")