"""
Módulo Central de Sincronização e Gestão de Dados (OÁSIS).

Centraliza todas as operações de coleta, sincronização incremental,
vetorização delta e atualização de cache do sistema.
"""

import os
import json
import glob
import pickle
import torch
import argparse
import config
from datetime import datetime
import coletor_camara2
from embeddings import get_model
from utils_legislativo import limpar_ementa_para_vetorizacao

class SyncManager:
    def __init__(self):
        self.pasta_dados = config.PASTA_DADOS

    def sync_tramitacoes(self, status_callback=None):
        """Atualiza apenas o histórico recente de andamentos e status."""
        if status_callback: 
            status_callback("🔄 Sincronizando histórico de tramitações e status recentes...")
        
        coletor_camara2.atualizar_historico_tramitacoes()
        return "✅ Tramitações e status atualizados com sucesso!"

    def sync_delta_vetores(self, pbar_callback=None, status_callback=None):
        """Vetoriza APENAS novos projetos não indexados no cache .pkl."""
        if status_callback: 
            status_callback("🧠 Verificando vetores e embeddings pendentes...")
        
        model = get_model()
        padrao = os.path.join(self.pasta_dados, "camara_db_leg*.json")
        arquivos_json = glob.glob(padrao)

        total_novos_vetorizados = 0

        for arquivo_json in arquivos_json:
            sufixo = os.path.basename(arquivo_json).replace("camara_db_", "").replace(".json", "")
            arquivo_pkl = os.path.join(self.pasta_dados, f"cache_ementas_{sufixo}.pkl")

            with open(arquivo_json, 'r', encoding='utf-8') as f:
                dados_json = json.load(f)

            embeddings_existentes = None
            qtd_existente = 0

            if os.path.exists(arquivo_pkl):
                with open(arquivo_pkl, 'rb') as f:
                    embeddings_existentes = pickle.load(f)
                    qtd_existente = len(embeddings_existentes)

            total_json = len(dados_json)

            if total_json > qtd_existente:
                novos_projetos = dados_json[qtd_existente:]
                if status_callback:
                    status_callback(f"⚡ Vetorizando {len(novos_projetos)} novos projetos na {sufixo}...")

                ementas_novas = [
                    limpar_ementa_para_vetorizacao(p.get('ementa', ''))
                    for p in novos_projetos
                ]

                novos_embeddings = model.encode(
                    ementas_novas,
                    convert_to_tensor=True,
                    show_progress_bar=False,
                    batch_size=64
                ).cpu()

                if embeddings_existentes is not None:
                    embeddings_finais = torch.cat([embeddings_existentes, novos_embeddings], dim=0)
                else:
                    embeddings_finais = novos_embeddings

                with open(arquivo_pkl, 'wb') as f:
                    pickle.dump(embeddings_finais, f)

                total_novos_vetorizados += len(novos_projetos)

        return f"✅ Vetorização concluída. {total_novos_vetorizados} novos embeddings adicionados."

    def sync_novos_projetos(self, pbar_callback=None, status_callback=None, forcar_do_zero=False):
        """Coleta novas proposições na API e dispara a vetorização delta."""
        if forcar_do_zero:
            arquivo_meta = os.path.join(self.pasta_dados, "metadata_coleta.json")
            if os.path.exists(arquivo_meta):
                os.remove(arquivo_meta)
            if status_callback: 
                status_callback("⚠️ Modo Recoleta do Zero ativado. Buscando toda a base histórica...")
        else:
            if status_callback: 
                status_callback("📡 Buscando novas proposições na API da Câmara...")
        
        coletor_camara2.executar_coleta_incremental()
        msg_vetores = self.sync_delta_vetores(pbar_callback, status_callback)
        return f"✅ Coleta e vetorização finalizadas! ({msg_vetores})"

    def sync_completo(self, pbar_callback=None, status_callback=None, forcar_do_zero=False):
        """Executa toda a esteira de atualização."""
        self.sync_novos_projetos(pbar_callback, status_callback, forcar_do_zero=forcar_do_zero)
        self.sync_tramitacoes(status_callback)
        return "✅ Base de dados completamente sincronizada e pronta para uso!"

# =========================================================================
# BLOCO DE EXECUÇÃO VIA TERMINAL / LINHA DE COMANDO
# =========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerenciador de Sincronização OÁSIS (Execução Interna/Admin)")
    parser.add_argument(
        "--modo", 
        choices=["tramitacoes", "novos", "completo"], 
        default="completo",
        help="Escolha o tipo de sincronização a ser executada"
    )
    parser.add_argument(
        "--do-zero", 
        action="store_true", 
        help="Ignora a data do metadata_coleta.json e força re-coleta completa desde config.DATA_INICIO_COLETA"
    )

    args = parser.parse_args()
    sync = SyncManager()

    print(f"\n--- INICIANDO ATUALIZAÇÃO OÁSIS (Modo: {args.modo.upper()}) ---")

    if args.modo == "tramitacoes":
        resultado = sync.sync_tramitacoes(status_callback=print)
    elif args.modo == "novos":
        resultado = sync.sync_novos_projetos(status_callback=print, forcar_do_zero=args.do_zero)
    elif args.modo == "completo":
        resultado = sync.sync_completo(status_callback=print, forcar_do_zero=args.do_zero)

    print(f"\n{resultado}")