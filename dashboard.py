import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import date


# ==============================================
# 1) CONFIGURAÇÃO BÁSICA DO APP
# ==============================================
st.set_page_config(
    page_title="Dashboard dos Projetos de Lei",
    layout="wide"
)

st.title("Dashboard dos Projetos de Lei da Câmara dos Deputados - OASIS")


# ==============================================
# 2) CONEXÃO E FUNÇÕES AUXILIARES
# ==============================================
@st.cache_data
def load_data(query):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password=" ",
        database="Oasis"
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
    df = load_data(query)
    return df[coluna].tolist()

@st.cache_data
def load_min_date():
    query = """
    SELECT MIN(datadeapresentacao) AS min_date
    FROM Projetos
    WHERE datadeapresentacao IS NOT NULL;
    """
    df = load_data(query)
    return df["min_date"].iloc[0]

@st.cache_data
def load_max_date():
    query = """
    SELECT MAX(datadeapresentacao) AS max_date
    FROM Projetos
    WHERE datadeapresentacao IS NOT NULL;
    """
    df = load_data(query)
    return df["max_date"].iloc[0]


# ==============================================
# 3) SIDEBAR — FILTROS
# ==============================================
st.sidebar.header("⚙️ Filtros")

data_inicio = st.sidebar.date_input(
    "Data inicial",
    value=load_min_date()
)

data_fim = st.sidebar.date_input(
    "Data final",
    value=load_max_date()
)

lista_partidos = load_distinct_values("partido")
lista_situacoes = load_distinct_values("situacao")

partido_filtro = st.sidebar.multiselect("Partido", lista_partidos)
situacao_filtro = st.sidebar.multiselect("Situação", lista_situacoes)

keyword = st.sidebar.text_input("Palavra-chave (ementa / indexação)")

st.sidebar.markdown("---")

st.sidebar.subheader("📊 Gráficos")

show_graf_ano = st.sidebar.checkbox("Projetos por ano", value=True)
show_graf_partido = st.sidebar.checkbox("Projetos por partido", value=True)
show_graf_autores = st.sidebar.checkbox("Projetos por autor", value=True)
show_graf_descricao = st.sidebar.checkbox("Projetos por descrição", value=True)
show_graf_situacao = st.sidebar.checkbox("Situação dos projetos", value=True)


# ==============================================
# 4) FUNÇÃO CENTRAL DE FILTROS (CAMADA SEMÂNTICA)
# ==============================================
def build_where_clause():
    conditions = [
        f"datadeapresentacao BETWEEN '{data_inicio}' AND '{data_fim}'"
    ]

    if  partido_filtro:
        partido_filtro_sql = ", ".join(f"'{p}'" for p in partido_filtro)
        conditions.append(f"partido IN ({partido_filtro_sql})")

    if situacao_filtro:
        situacao_filtro_sql = ", ".join(f"'{s}'" for s in situacao_filtro)
        conditions.append(f"situacao IN ({situacao_filtro_sql})")

    if keyword:
        conditions.append(
            f"(ementa LIKE '%{keyword}%' "
            f"OR indexacao LIKE '%{keyword}%')"
        )

    return " WHERE " + " AND ".join(conditions)


# ==============================================
# 5) TABS
# ==============================================
tab_visaoGeral, tab_partidos, tab_autores, tab_temas, tab_proposicoes = st.tabs([
    "📈 Visão Geral",
    "🏛️ Partidos",
    "✍️ Autores",
    "📝 Temas",
    "📄 Proposições"
])


# ==============================================
# TAB 1 — VISÃO GERAL
# ==============================================
with tab_visaoGeral:
    st.header("📈 Visão Geral")

    if show_graf_ano:
        query = f"""
        SELECT YEAR(datadeapresentacao) AS ano, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        GROUP BY YEAR(datadeapresentacao)
        ORDER BY ano;
        """
        df = load_data(query)

        fig = px.line(df, x="ano", y="quantidade",
                      title="Projetos por ano", markers=True)
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 2 — PARTIDOS
# ==============================================
with tab_partidos:
    st.header("🏛️ Projetos por Partido")

    if show_graf_partido:
        query = f"""
        SELECT partido, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        AND partido IS NOT NULL AND partido <> ''
        GROUP BY partido
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        fig = px.bar(
            df,
            x="quantidade",
            y="partido",
            orientation="h",
            title="Projetos por Partido"
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            height=800
        )

        st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 3 — AUTORES
# ==============================================
with tab_autores:
    st.header("✍️ Projetos por Autor")

    if show_graf_autores:
        query = f"""
        SELECT autor, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        AND autor IS NOT NULL AND autor <> ''
        GROUP BY autor
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        st.dataframe(df, use_container_width=True)

        df_top = df.head(20)
        fig = px.bar(
            df_top,
            x="quantidade",
            y="autor",
            orientation="h",
            title="Top 20 Autores"
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            height=800
        )
        st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 4 — TEMAS / SITUAÇÃO
# ==============================================
with tab_temas:
    st.header("📝 Temas e Situação")

    if show_graf_descricao:
        query = f"""
        SELECT descricao, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        AND descricao IS NOT NULL AND descricao <> ''
        GROUP BY descricao
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        fig = px.bar(df, x="descricao", y="quantidade",
                     title="Projetos por Descrição")
        st.plotly_chart(fig, use_container_width=True)

    if show_graf_situacao:
        query = f"""
        SELECT situacao, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        AND situacao IS NOT NULL AND situacao <> ''
        GROUP BY situacao
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        col1, col2 = st.columns(2)

        with col1:
            fig = px.pie(df, names="situacao", values="quantidade",
                         hole=0.4, title="Situação dos Projetos")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(df, x="quantidade", y="situacao",
                         orientation="h",
                         title="Quantidade por Situação")
            st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 5 — PROPOSIÇÕES
# ==============================================
with tab_proposicoes:
    st.header("📄 Proposições")

    st.markdown(
        "Use os filtros na barra lateral e clique em **Buscar proposições**."
    )

    if st.button("🔍 Buscar proposições"):
        query = f"""
        SELECT
            norma,
            autor,
            partido,
            situacao,
            datadeapresentacao,
            ementa,
            indexacao,
            linkweb
        FROM Projetos
        {build_where_clause()}
        ORDER BY datadeapresentacao DESC
        """

        df = load_data(query)

        if df.empty:
            st.warning("Nenhuma proposição encontrada.")
        else:
            st.success(f"{len(df)} proposições encontradas.")

            df = df.rename(columns={
                "norma": "Proposição",
                "autor": "Autor",
                "partido": "Partido",
                "situacao": "Situação",
                "datadeapresentacao": "Data",
                "linkweb": "Link"
            })

            st.dataframe(df, use_container_width=True)
