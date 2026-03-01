import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import date
import config

# ==============================================
# 1) CONFIGURAÇÃO BÁSICA DO APP
# ==============================================
st.set_page_config(
    page_title="Dashboard OASIS",
    layout="wide"
)

st.title("🏛️ Dashboard dos Projetos de Lei - IA OASIS")
st.markdown("Visualização das proposições filtradas e classificadas pela Inteligência Artificial.")

# ==============================================
# 2) CONEXÃO E FUNÇÕES AUXILIARES
# ==============================================
@st.cache_data
def load_data(query):
    conn = mysql.connector.connect(
        host=config.HOST,
        user=config.USUARIO,
        password=config.SENHA,
        database=config.NOME
    )
    return pd.read_sql(query, conn)

@st.cache_data
def load_distinct_values(coluna):
    query = f"""
    SELECT DISTINCT {coluna}
    FROM Projetos
    WHERE {coluna} IS NOT NULL AND {coluna} <> ''
    ORDER BY {coluna};
    """
    try:
        df = load_data(query)
        return ["Todos"] + df[coluna].tolist()
    except:
        return ["Todos"]

@st.cache_data
def load_min_date():
    query = "SELECT MIN(datadeapresentacao) AS min_date FROM Projetos;"
    try:
        df = load_data(query)
        if not df.empty and pd.notnull(df.iloc[0]['min_date']):
            return df.iloc[0]['min_date']
    except:
        pass
    return date(2000, 1, 1)

# ==============================================
# 3) SIDEBAR — FILTROS
# ==============================================
st.sidebar.header("⚙️ Filtros do Painel")

# --- NOVO: Filtro por Número da Norma ---
numero_norma = st.sidebar.text_input("Número da Norma (Ex: PL 2338/2023 ou 2338)")

# Carrega opções dinâmicas do banco
partidos_disponiveis = load_distinct_values("partido")
partido_filtro = st.sidebar.selectbox("Partido do Autor", partidos_disponiveis)

situacoes_disponiveis = load_distinct_values("situacao")
situacao_filtro = st.sidebar.selectbox("Situação da Proposição", situacoes_disponiveis)

keyword = st.sidebar.text_input("Palavra-chave extra (Opcional)")

min_data_db = load_min_date()
data_inicio = st.sidebar.date_input("Data Início", min_data_db)
data_fim = st.sidebar.date_input("Data Fim", date.today())

def build_where_clause():
    """Constrói a cláusula WHERE do SQL dinamicamente."""
    clausulas = [f"datadeapresentacao BETWEEN '{data_inicio}' AND '{data_fim}'"]
    
    # --- NOVA REGRA DO FILTRO AQUI ---
    if numero_norma:
        # Usamos LIKE para permitir que o usuário digite apenas "2338" ou "PL 2338/2023"
        clausulas.append(f"norma LIKE '%{numero_norma}%'")
        
    if partido_filtro != "Todos":
        clausulas.append(f"partido = '{partido_filtro}'")
        
    if situacao_filtro != "Todos":
        clausulas.append(f"situacao = '{situacao_filtro}'")
        
    if keyword:
        clausulas.append(f"""
        (ementa LIKE '%{keyword}%' 
         OR indexacao LIKE '%{keyword}%' 
         OR descricao LIKE '%{keyword}%')
        """)
        
    return "WHERE " + " AND ".join(clausulas)

# ==============================================
# 4) ESTRUTURA DE ABAS
# ==============================================
tab_visao, tab_proposicoes = st.tabs(["📊 Visão Geral", "📄 Lista de Proposições"])

# --- ABA 1: VISÃO GERAL ---
with tab_visao:
    st.subheader("Métricas do Tema Filtrado")

    query_visao = f"""
    SELECT partido, situacao, COUNT(*) as quantidade
    FROM Projetos
    {build_where_clause()}
    GROUP BY partido, situacao
    """
    df_visao = load_data(query_visao)

    if df_visao.empty:
        st.warning("Nenhum dado encontrado com os filtros atuais.")
    else:
        total_projetos = int(df_visao['quantidade'].sum())
        total_partidos = df_visao['partido'].nunique()
        
        col1, col2 = st.columns(2)
        col1.metric("Total de Projetos Relevantes (IA)", total_projetos)
        col2.metric("Partidos Envolvidos", total_partidos)

        st.markdown("---")

        col_graf1, col_graf2 = st.columns(2)

        with col_graf1:
            df_partido = df_visao.groupby('partido', as_index=False)['quantidade'].sum()
            df_partido = df_partido.sort_values(by='quantidade', ascending=False).head(10)
            fig1 = px.bar(df_partido, x="partido", y="quantidade",
                         title="Top 10 Partidos com Mais Projetos",
                         labels={"partido": "Partido", "quantidade": "Projetos"})
            st.plotly_chart(fig1, use_container_width=True)

        with col_graf2:
            df_sit = df_visao.groupby('situacao', as_index=False)['quantidade'].sum()
            fig2 = px.pie(df_sit, values="quantidade", names="situacao",
                         title="Distribuição por Situação Atual")
            st.plotly_chart(fig2, use_container_width=True)

# --- ABA 2: PROPOSIÇÕES ---
# --- ABA 2: PROPOSIÇÕES ---
with tab_proposicoes:
    st.subheader("Detalhamento dos Projetos")

    query_props = f"""
    SELECT
        score_relevancia as "Relevância (IA)",
        norma as "Norma",
        autor as "Autor",
        partido as "Partido",
        situacao as "Situação",
        datadeapresentacao as "Data",
        ementa as "Ementa",
        linkweb as "Link"
    FROM Projetos
    {build_where_clause()}
    ORDER BY score_relevancia DESC
    """
    df_props = load_data(query_props)

    if df_props.empty:
        st.warning("Nenhuma proposição encontrada.")
    else:
        st.dataframe(
            df_props,
            column_config={
                "Link": st.column_config.LinkColumn("Link da Câmara")
            },
            use_container_width=True,
            hide_index=True
        )