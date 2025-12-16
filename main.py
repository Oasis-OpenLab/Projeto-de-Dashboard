import subprocess
import os
import shutil
import mysql.connector
import sys

# --- CONFIGURAÇÃO GLOBAL DE CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "dudu2004"

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
            print(f"Pasta criada: {pasta_csv}")
        except OSError as e:
            print(f"Erro ao criar pasta: {e}")
    else:
        print(f"Pasta já existe: {pasta_csv}")

def executar_api():
    print("\n>>> [1/4] Coletando dados da API (acess_api.py)...")
    
    script_path = obter_caminho("acess_api.py")
    
    subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
    
    # Movimentação do arquivo
    arquivo_gerado = obter_caminho("proposicoes_camara_resumo.csv")
    pasta_destino = obter_caminho("projetos_em_csv")
    destino_final = os.path.join(pasta_destino, "proposicoes_camara_resumo.csv")
    
    if os.path.exists(arquivo_gerado):
        # Remove versão antiga se existir para evitar conflito
        if os.path.exists(destino_final):
            os.remove(destino_final)

        shutil.move(arquivo_gerado, destino_final)
        print(f"Arquivo CSV movido para: {destino_final}")
    else:
        print("AVISO: O arquivo CSV não foi gerado pela API (ou foi salvo em outro lugar).")

def recriar_banco():
    print("\n>>> [2/4] Recriando Banco de Dados (create_database.sql)...")
    
    arquivo_sql = obter_caminho("create_database.sql")

    if not os.path.exists(arquivo_sql):
        print(f"Erro: Arquivo não encontrado: {arquivo_sql}")
        return

    with open(arquivo_sql, "r", encoding="utf-8") as f:
        sql_script = f.read()

    try:
        cnx = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = cnx.cursor()
        
        commands = sql_script.split(';')
        
        for command in commands:
            if command.strip():
                try:
                    cursor.execute(command)
                except mysql.connector.Error as err:
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
        sys.exit(1)

def inserir_dados():
    print("\n>>> [3/4] Inserindo dados no SQL (insert_data.py)...")
    script_path = obter_caminho("insert_data.py")
    
    try:
        subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
    except subprocess.CalledProcessError:
        print("Erro ao inserir dados. Verifique a senha ou o código.")
        sys.exit(1)

def abrir_dashboard():
    print("\n>>> [4/4] Iniciando Dashboard (Streamlit)...")
    print("Pressione Ctrl+C no terminal para encerrar o servidor.")
    
    dashboard_path = obter_caminho("dashboard.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path], check=True, cwd=BASE_DIR)

if __name__ == "__main__":
    print(f"--- INICIANDO PIPELINE DE DADOS OASIS ---")
    print(f"Diretório base: {BASE_DIR}")
    
    # 0. Garante que a pasta existe antes de tudo
    garantir_estrutura_pastas()
    
    # 1. Coleta
    executar_api()
    
    # 2. Banco
    recriar_banco()
    
    # 3. Inserção
    inserir_dados()
    
    # 4. Dashboard
    abrir_dashboard()