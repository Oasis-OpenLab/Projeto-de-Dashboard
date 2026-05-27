import mysql.connector
import json
import os
import config

def conectar_banco():
    return mysql.connector.connect(
        host=config.HOST,
        user=config.USUARIO,
        password=config.SENHA,
        database=config.NOME,
        port=config.porta,
        ssl_ca=config.certificado
    )

def rodar_atualizacao_isolada():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    print("🔄 Iniciando atualização das tramitações via Cache JSON...")
    
    # 1. Busca todas as normas dos projetos que estão no banco atual
    cursor.execute("SELECT norma FROM Projetos;")
    projetos = cursor.fetchall()
    
    if not projetos:
        print("⚠️ Nenhum projeto encontrado na tabela principal para atualizar.")
        cursor.close()
        conn.close()
        return

    # 2. Limpa o histórico anterior no banco
    print("🧹 Limpando histórico de tramitações antigo do MySQL...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Tramitacoes;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    
    # 3. Carrega o cache JSON gigante gerado pelo coletor
    arquivo_cache = os.path.join(config.PASTA_DADOS, "camara_tramitacoes_cache.json")
    if not os.path.exists(arquivo_cache):
        print("⚠️ ERRO: Arquivo de cache JSON não encontrado. Rode a coleta completa primeiro.")
        cursor.close()
        conn.close()
        return
        
    with open(arquivo_cache, 'r', encoding='utf-8') as f:
        cache_tramitacoes = json.load(f)

    # 4. Cruza os dados do banco com o JSON e insere no MySQL
    for (norma,) in projetos:
        # Padroniza a string removendo espaços invisíveis para garantir o 'match' exato com o JSON
        chave_busca = str(norma).upper().strip()
        historico_projeto = cache_tramitacoes.get(chave_busca, [])
        
        if not historico_projeto:
            print(f"⚠️ Sem histórico em cache para: '{norma}' (Chave buscada: '{chave_busca}')")
            continue
            
        print(f"🛰️ Inserindo andamentos de: {norma} (Via JSON)")
        for t in historico_projeto:
            query = """
            INSERT INTO Tramitacoes (norma, data_tramitacao, sequencia, orgao, descricao_tramitacao, situacao_tramitacao, apreciacao, despacho)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            valores = (
                norma,
                t.get('data_tramitacao'),
                t.get('sequencia'),
                t.get('orgao'),
                t.get('descricao_tramitacao'),
                t.get('situacao_tramitacao'),
                t.get('apreciacao'),
                t.get('despacho')
            )
            cursor.execute(query, valores)
    
    conn.commit()        
    cursor.close()
    conn.close()
    print("✅ Histórico de tramitações populado no banco com sucesso!")

if __name__ == "__main__":
    rodar_atualizacao_isolada()