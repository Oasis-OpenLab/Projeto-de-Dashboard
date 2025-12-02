import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px

# ==============================================
# 1) CONFIGURAÇÃO BÁSICA DO APP
# ==============================================
st.set_page_config(
    page_title="Dashboard dos Projetos de Lei",
    layout="wide"  # usa a largura total da tela
)

st.title("Dashboard dos Projetos de Lei da Câmara dos Deputados - OASIS")


# ==============================================
# 2) SIDEBAR (FILTROS E OPÇÕES)
# ==============================================
st.sidebar.header("⚙️ Filtros e Opções")

# Conexão ao MySQL
@st.cache_data
def load_data(query):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="dudu2004",
        database="Oasis"
    )
    return pd.read_sql(query, conn)

# → Filtro de ANO
ano_min = st.sidebar.number_input("Ano mínimo", min_value=1900, max_value=2100, value=2000)
ano_max = st.sidebar.number_input("Ano máximo", min_value=1900, max_value=2100, value=2030)

# → Filtro de PARTIDO
partido_filtro = st.sidebar.text_input("Filtrar por Partido (opcional)")

# → Filtro por SITUAÇÃO
situacao_filtro = st.sidebar.text_input("Filtrar por Situação (opcional)")

# → Palavra-chave na indexação
keyword = st.sidebar.text_input("Buscar palavra-chave (indexação ou ementa)")

st.sidebar.markdown("---")

# → Seleção de gráficos (checkbox)
st.sidebar.subheader("📊 Escolha os gráficos que quer ver:")

show_graf_ano = st.sidebar.checkbox("Projetos por ano", value=True)
show_graf_partido = st.sidebar.checkbox("Distribuição por partido", value=True)
show_graf_descricao = st.sidebar.checkbox("Projetos por descrição", value=True)
show_graf_autores = st.sidebar.checkbox("Top autores", value=True)
show_graf_situacao = st.sidebar.checkbox("Situação dos projetos", value=True)


# ==============================================
# 3) TABS DO DASHBOARD
# ==============================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Visão Geral",
    "🏛️ Partidos",
    "✍️ Autores",
    "📝 Temas/Descrições"
])


# =========================================================
# 4) TAB 1 — VISÃO GERAL
# =========================================================
with tab1:
    st.header("📈 Visão Geral dos Projetos de Lei")

    # -------------------------------
    # Gráfico: Projetos por ano
    # -------------------------------
    if show_graf_ano:
        query = f"""
        SELECT YEAR(datadeapresentacao) AS ano, COUNT(*) AS quantidade
        FROM Projetos
        WHERE datadeapresentacao IS NOT NULL
        AND YEAR(datadeapresentacao) BETWEEN {ano_min} AND {ano_max}
        GROUP BY YEAR(datadeapresentacao)
        ORDER BY ano;
        """

        df = load_data(query)

        fig = px.line(df, x="ano", y="quantidade",
                      title="Número de Projetos Apresentados por Ano")
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# 5) TAB 2 — PARTIDOS
# =========================================================
with tab2:
    st.header("🏛️ Projetos por Partido")

    if show_graf_partido:
        query = f"""
        SELECT partido, COUNT(*) AS quantidade
        FROM Projetos
        WHERE partido IS NOT NULL AND partido <> ''
        GROUP BY partido
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        # Filtro opcional por partido
        if partido_filtro:
            df = df[df["partido"].str.contains(partido_filtro, case=False)]

        col1, col2 = st.columns(2)

        with col1:
            fig = px.pie(df, names="partido", values="quantidade",
                         title="Distribuição de Projetos por Partido")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.bar(df, x="quantidade", y="partido", orientation="h",
                          title="Projetos por Partido (Barra)")
            st.plotly_chart(fig2, use_container_width=True)


# =========================================================
# 6) TAB 3 — AUTORES
# =========================================================
with tab3:
    st.header("✍️ Projetos por Autor")

    if show_graf_autores:
        query = """
        SELECT autor, COUNT(*) AS quantidade
        FROM Projetos
        WHERE autor IS NOT NULL AND autor <> ''
        GROUP BY autor
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        # Mostra tabela completa
        st.dataframe(df)

        # Top 20 autores
        df_top = df.head(20)

        fig = px.bar(df_top, x="quantidade", y="autor",
                     orientation="h", title="Top 20 Autores com Mais Projetos")
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})

        st.plotly_chart(fig, use_container_width=True)


# =========================================================
# 7) TAB 4 — DESCRIÇÕES / TEMAS
# =========================================================
with tab4:
    st.header("📝 Projetos por Descrição / Tema")

    if show_graf_descricao:
        query = """
        SELECT descricao, COUNT(*) AS quantidade
        FROM Projetos
        WHERE descricao IS NOT NULL AND descricao <> ''
        GROUP BY descricao
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        # Barra
        fig = px.bar(df, x="descricao", y="quantidade",
                     title="Número de Projetos por Descrição da Sigla")
        st.plotly_chart(fig, use_container_width=True)

    # -------------------------
    # Situação dos projetos
    # -------------------------
    if show_graf_situacao:
        st.subheader("Situação dos Projetos")

        query = """
        SELECT situacao, COUNT(*) AS quantidade
        FROM Projetos
        WHERE situacao IS NOT NULL AND situacao <> ''
        GROUP BY situacao
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        # Filtro opcional
        if situacao_filtro:
            df = df[df["situacao"].str.contains(situacao_filtro, case=False)]

        total = df["quantidade"].sum()
        df["porcentagem"] = (df["quantidade"] / total * 100).round(2)

        # Layout em duas colunas
        col1, col2 = st.columns(2)

        with col1:
            fig_pie = px.pie(df, names="situacao", values="quantidade",
                             title="Distribuição Percentual por Situação",
                             hole=0.4)
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            fig_bar = px.bar(df, x="quantidade", y="situacao",
                             orientation="h",
                             title="Quantidade Absoluta por Situação")
            st.plotly_chart(fig_bar, use_container_width=True)
