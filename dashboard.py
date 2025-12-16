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
        user="fabiocs",
        password="Fcs@26734103",
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
    return ["Todos"] + df[coluna].tolist()


# ==============================================
# 3) SIDEBAR — FILTROS
# ==============================================
st.sidebar.header("⚙️ Filtros")

# → Filtro de intervalo de datas
data_inicio = st.sidebar.date_input(
    "Data inicial",
    value=date(2020, 1, 1)
)

data_fim = st.sidebar.date_input(
    "Data final",
    value=date.today()
)

# → Filtros guiados
lista_partidos = load_distinct_values("partido")
lista_situacoes = load_distinct_values("situacao")

partido_filtro = st.sidebar.selectbox("Partido", lista_partidos)
situacao_filtro = st.sidebar.selectbox("Situação", lista_situacoes)

# → Palavra-chave
keyword = st.sidebar.text_input("Palavra-chave (ementa / indexação)")

st.sidebar.markdown("---")

# → Seleção de gráficos
st.sidebar.subheader("📊 Gráficos")

show_graf_ano = st.sidebar.checkbox("Projetos por ano", value=True)
show_graf_partido = st.sidebar.checkbox("Distribuição por partido", value=True)
show_graf_descricao = st.sidebar.checkbox("Projetos por descrição", value=True)
show_graf_autores = st.sidebar.checkbox("Top autores", value=True)
show_graf_situacao = st.sidebar.checkbox("Situação dos projetos", value=True)


# ==============================================
# 4) TABS
# ==============================================
tab1, tab2, tab3, tab4, aba_proposicoes = st.tabs([
    "📈 Visão Geral",
    "🏛️ Partidos",
    "✍️ Autores",
    "📝 Temas",
    "📄 Proposições"
])


# ==============================================
# TAB 1 — VISÃO GERAL
# ==============================================
with tab1:
    st.header("📈 Visão Geral")

    if show_graf_ano:
        query = f"""
        SELECT YEAR(datadeapresentacao) AS ano, COUNT(*) AS quantidade
        FROM Projetos
        WHERE datadeapresentacao BETWEEN '{data_inicio}' AND '{data_fim}'
        GROUP BY YEAR(datadeapresentacao)
        ORDER BY ano;
        """
        df = load_data(query)
        print(df)
        fig = px.line(df, x="ano", y="quantidade",
                      title="Projetos apresentados por ano")
        fig.update_xaxes(dtick=1)
        st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 2 — PARTIDOS
# ==============================================
with tab2:
    st.header("🏛️ Projetos por Partido")

    if show_graf_partido:
        query = """
        SELECT partido, COUNT(*) AS quantidade
        FROM Projetos
        WHERE partido IS NOT NULL AND partido <> ''
        GROUP BY partido
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        col1, col2 = st.columns(2)

        with col1:
            fig = px.treemap(
                df,
                path=["partido"],
                values="quantidade",
                title="Distribuição por Partido"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                df,
                x="quantidade",
                y="partido",
                orientation="h",
                title="Projetos por Partido"
            )
            st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 3 — AUTORES
# ==============================================
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

        st.dataframe(df, use_container_width=True)

        df_top = df.head(20)
        fig = px.bar(
            df_top,
            x="quantidade",
            y="autor",
            orientation="h",
            title="Top 20 Autores"
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)


# ==============================================
# TAB 4 — TEMAS / SITUAÇÃO
# ==============================================
with tab4:
    st.header("📝 Temas e Situação")

    if show_graf_descricao:
        query = """
        SELECT descricao, COUNT(*) AS quantidade
        FROM Projetos
        WHERE descricao IS NOT NULL AND descricao <> ''
        GROUP BY descricao
        ORDER BY quantidade DESC;
        """
        df = load_data(query)

        fig = px.bar(df, x="descricao", y="quantidade",
                     title="Projetos por Descrição")
        st.plotly_chart(fig, use_container_width=True)

    if show_graf_situacao:
        query = """
        SELECT situacao, COUNT(*) AS quantidade
        FROM Projetos
        WHERE situacao IS NOT NULL AND situacao <> ''
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
with aba_proposicoes:
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
            linkweb
        FROM Projetos
        WHERE datadeapresentacao BETWEEN '{data_inicio}' AND '{data_fim}'
        """

        if partido_filtro != "Todos":
            query += f" AND partido = '{partido_filtro}'"

        if situacao_filtro != "Todos":
            query += f" AND situacao = '{situacao_filtro}'"

        if keyword:
            query += f"""
            AND (
                ementa LIKE '%{keyword}%'
                OR indexacao LIKE '%{keyword}%'
                OR descricao LIKE '%{keyword}%'
            )
            """

        query += " ORDER BY datadeapresentacao DESC"

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
