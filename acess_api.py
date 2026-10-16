import sys
import os
import argparse
import coletor_camara2
import embeddings
import gerador_keywords

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Completo de Atualização da Base de Dados OÁSIS")
    parser.add_argument(
        "--modo", 
        choices=["full", "incremental"], 
        default="incremental",
        help="'full' para recriar base inteira do zero ou 'incremental' para atualizar apenas a última legislatura."
    )
    args = parser.parse_args()

    print(f"\n========================================================")
    print(f"🚀 INICIANDO ATUALIZAÇÃO DA BASE DE DADOS (MODO: {args.modo.upper()})")
    print(f"========================================================\n")

    # 1. Coleta e Tramitações na API
    print(">>> 1/3: Coletando projetos e atualizando históricos...")
    coletor_camara2.executar_coleta_incremental(modo=args.modo)

    # 2. Geração dos Embeddings das Ementas
    print("\n>>> 2/3: Processando embeddings de ementas...")
    embeddings.processar_embeddings(modo=args.modo, legislatura="leg57")

    # 3. Geração dos Embeddings de Keywords
    print("\n>>> 3/3: Processando embeddings de palavras-chave...")
    gerador_keywords.processar_keywords(modo=args.modo, legislatura="leg57")

    print(f"\n✅ PIPELINE DE ATUALIZAÇÃO DA BASE ({args.modo.upper()}) FINALIZADO COM SUCESSO!\n")
