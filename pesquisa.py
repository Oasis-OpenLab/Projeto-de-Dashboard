"""
Orquestrador Principal do Backend (Controlador de Pesquisa).

É o elo entre a interface do usuário (Streamlit) e o processamento pesado.
Quando acionado, garante que a estrutura de pastas exista e dispara, na ordem correta:
1. O sub-orquestrador de IA (Pipeline Híbrido).
2. O script de recriação limpa do Banco de Dados.
3. O script de inserção dos novos resultados no MySQL.
"""
import subprocess
import os
import mysql.connector
import sys
import config
import streamlit as st

def pesquisar():
    """
    Controlador mestre que executa o fluxo completo da aplicação (End-to-End).

    Esta função engloba subfunções de utilidade para modularizar o processo:
    - garantir_estrutura_pastas(): Evita erros de I/O na gravação do CSV.
    - executar_api(): Roda o motor de Machine Learning.
    - recriar_banco(): Executa o .sql bruto para formatar as tabelas.
    - inserir_dados(): Move o CSV processado para as tabelas recém-criadas.
    """
    
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
                host=config.HOST,
                database=config.NOME,
                port = config.porta,
                ssl_ca = config.certificado
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
        print("\n>>> [3/5] Inserindo dados filtrados no SQL (insert_data.py)...")
        script_path = obter_caminho("insert_data.py")
        try:
            subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
        except subprocess.CalledProcessError:
            print("Erro ao inserir dados. Verifique o arquivo insert_data.py.")
            sys.exit(1)

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

        # 4. Busca o histórico de tramitações no JSON e insere no Banco
        # atualizar_tramitacoes()
            
    except Exception as e:
        print(f"Ocorreu um erro fatal na execução principal: {e}")