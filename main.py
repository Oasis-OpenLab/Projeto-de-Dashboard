import streamlit as st

import dashboard
import os
import glob
import config
import time
from sync_manager import SyncManager

# Instancia o gerenciador central
sync = SyncManager()

st.set_page_config(page_title="Dashboard OASIS", layout="wide")
st.title("🏛️ Dashboard dos Projetos de Lei - IA OASIS")

# Inicializa estados de controle
if 'ia_concluida' not in st.session_state:
    st.session_state.ia_concluida = False
if 'atualizando_db' not in st.session_state:
    st.session_state.atualizando_db = False

tab_pesquisa, tab_bd = st.tabs([
    "📊 Pesquisa", 
    "📄 Atualizar Base de Dados (BETA)", 
])

with tab_pesquisa:
    # ---------------------------------------------------------
    # 1) PESQUISA INTELIGENTE (FILTRAGEM POR IA)
    # ---------------------------------------------------------
    st.subheader("🧠 Pesquisa Inteligente com IA")

    # Bloqueia a pesquisa se o banco estiver sendo atualizado
    if st.session_state.atualizando_db:
        st.warning("⚠️ Base de dados em atualização. Por favor, aguarde a conclusão na outra aba.")
    
    col1, col2 = st.columns(2)
    with col1:
        tema_pesquisa_principal = st.text_input("Tema principal:", help="Peso maior na busca.")
    with col2:
        tema_pesquisa_secundaria = st.text_input("Tema secundário (opcional):")

    contexto_ia = st.text_input(
        "Direcionamento para a IA Especialista (Opcional):", 
        help="Ex: 'Quero foco apenas em responsabilização civil' ou 'Busque por regras tributárias'."
    )

    if st.button("Filtrar com IA", type="primary", disabled=st.session_state.atualizando_db):
        with st.spinner("Vetorizando pesquisa..."):
            import pesquisa
            from embeddings import get_model, gerar_embeddings_para_legislatura

            os.makedirs('banco_de_dados_local', exist_ok=True)
            with open('banco_de_dados_local/pesquisa1.txt', 'w', encoding='utf-8') as f:
                f.write(tema_pesquisa_principal)
            with open('banco_de_dados_local/pesquisa2.txt', 'w', encoding='utf-8') as f:
                f.write(tema_pesquisa_secundaria)
                
            with open('banco_de_dados_local/pesquisa_contexto.txt', 'w', encoding='utf-8') as f:
                f.write(contexto_ia)
                
            # Limpa o cache para esquecer o CSV antigo
            st.cache_data.clear() 
            
            # Roda todo o pipeline pesado (via subprocess)
            pesquisa.pesquisar()
            
            # Marca como concluído
            st.session_state.ia_concluida = True
            
        st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # 2) BUSCA AVULSA E DIRETA (POSICIONADA ABAIXO DO FILTRO)
    # ---------------------------------------------------------
    with st.expander("🔍 Busca Avulsa na Base Completa (Pesquisa Direta Sem Filtro)", expanded=True):
        dashboard.exibir_busca_global(key_suffix="inicio")

    st.markdown("---")

    if st.session_state.ia_concluida:
        dashboard.rodar_dashboard()

with tab_bd:
    st.subheader("⚙️ Painel Central de Sincronização de Dados")
    st.info("Escolha abaixo o nível de atualização desejado para a base de dados.")
    
    col1, col2, col3 = st.columns(3)

    # -------------------------------------------------------------------------
    # OPÇÃO 1: APENAS TRAMITAÇÕES (RÁPIDO)
    # -------------------------------------------------------------------------
    with col1:
        st.markdown("### ⚡ Rápido")
        st.caption("Atualiza apenas a situação e o histórico de andamento dos projetos já salvos. Não recalcula IA.")
        if st.button("Atualizar Tramitações", type="secondary", disabled=st.session_state.atualizando_db):
            st.session_state.atualizando_db = True
            status_info = st.empty()
            try:
                msg = sync.sync_tramitacoes(status_info.info)
                st.success(msg)
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao atualizar tramitações: {e}")
            finally:
                st.session_state.atualizando_db = False
                time.sleep(2)
                st.rerun()

    # -------------------------------------------------------------------------
    # OPÇÃO 2: INCREMENTAL (NOVOS PROJETOS + VETORES PENDENTES)
    # -------------------------------------------------------------------------
    with col2:
        st.markdown("### 🔍 Incremental")
        st.caption("Baixa novos projetos apresentados recentemente e vetoriza apenas as novas ementas.")
        if st.button("Buscar Novos Projetos", type="secondary", disabled=st.session_state.atualizando_db):
            st.session_state.atualizando_db = True
            status_info = st.empty()
            pbar = st.progress(0)
            try:
                msg = sync.sync_novos_projetos(pbar, status_info.info)
                st.success(msg)
                st.balloons()
            except Exception as e:
                st.error(f"Erro na sincronização incremental: {e}")
            finally:
                st.session_state.atualizando_db = False
                time.sleep(2)
                st.rerun()

    # -------------------------------------------------------------------------
    # OPÇÃO 3: COMPLETO (SINCRONIZAÇÃO TOTAL)
    # -------------------------------------------------------------------------
    with col3:
        st.markdown("### 🚀 Sincronização Total")
        st.caption("Executa toda a esteira de atualização (API, Vetores e Históricos) em sequência.")
        if st.button("Iniciar Atualização Total", type="primary", disabled=st.session_state.atualizando_db):
            st.session_state.atualizando_db = True
            status_info = st.empty()
            pbar = st.progress(0)
            try:
                msg = sync.sync_completo(pbar, status_info.info)
                st.success(msg)
                st.balloons()
            except Exception as e:
                st.error(f"Erro na sincronização total: {e}")
            finally:
                st.session_state.atualizando_db = False
                time.sleep(2)
                st.rerun()

    st.markdown("---")
    st.subheader("⚡ Atualização Rápida")
    st.info("Use esta opção para atualizar apenas o histórico de andamentos dos projetos já salvos, sem buscar projetos novos. É muito mais rápido.")
    
    if st.button("Atualizar APENAS Tramitações", type="secondary", disabled=st.session_state.atualizando_db):
        st.session_state.atualizando_db = True
        status_info = st.empty()
        
        try:
            import coletor_camara2 
            with st.spinner("🔄 Conectando à API da Câmara para baixar andamentos recentes..."):
                status_info.info("Baixando e compactando históricos (GZIP)... Pode levar alguns minutos.")
                coletor_camara2.atualizar_historico_tramitacoes()
                
            st.success("✅ Histórico de tramitações atualizado com sucesso!")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Erro crítico ao atualizar o histórico: {e}")
            
        finally:
            st.session_state.atualizando_db = False
            time.sleep(3) 
            st.rerun()