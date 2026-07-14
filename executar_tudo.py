import coletor_camara2
import embeddings
import insert_data
import pesquisa

print("Iniciando Pipeline Completo...")
coletor_camara2.executar_coleta_incremental() # Coleta e Tramitações[cite: 3]
embeddings.main() # Gera todos os .pkl[cite: 12]
# Se você tiver uma função que atualiza o MySQL, chame aqui também
print("Pipeline concluído com sucesso!")