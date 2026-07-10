"""
Script de Teste Unitário Interativo: Limpeza de Ementas
Objetivo: Validar o comportamento das funções de NLP do utils_legislativo.py
"""

import sys
import os

# Garante que o Python encontre o arquivo utils_legislativo.py no mesmo diretório
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from utils_legislativo import limpar_ementa_para_vetorizacao

def rodar_testador():
    print("=" * 60)
    print("🧪 TESTADOR DE LIMPEZA DE EMENTAS (OÁSIS) 🧪")
    print("=" * 60)
    print("Cole uma ementa para ver como a IA irá enxergá-la.")
    print("Digite 'sair' a qualquer momento para encerrar o programa.\n")

    while True:
        # Recebe o input do usuário
        ementa_original = input("📝 Cole a ementa original aqui:\n> ")
        
        # Condição de parada
        if ementa_original.strip().lower() == 'sair':
            print("\n👋 Encerrando o testador. Bom trabalho!")
            break
            
        if not ementa_original.strip():
            print("⚠️ Por favor, digite alguma coisa.\n")
            continue

        # Executa a função do seu módulo oficial
        ementa_limpa = limpar_ementa_para_vetorizacao(ementa_original)
        
        # Exibe o resultado de forma estruturada para fácil comparação
        print("\n" + "-" * 60)
        print("🔍 RESULTADO DA LIMPEZA")
        print("-" * 60)
        
        print(f"🔴 ANTES  ({len(ementa_original)} caracteres):")
        print(f"   {ementa_original}\n")
        
        print(f"🟢 DEPOIS ({len(ementa_limpa)} caracteres):")
        print(f"   {ementa_limpa}")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    rodar_testador()