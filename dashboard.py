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

# Filtro de texto para buscar pelo número exato ou parcial da norma (ex: PL 2338/2023 ou 2338)
numero_norma = st.sidebar.text_input("Norma")

# Carrega opções dinâmicas de partidos direto do banco de dados
partidos_disponiveis = load_distinct_values("partido")
partido_filtro = st.sidebar.selectbox("Partido do Autor", partidos_disponiveis)

# Filtro de texto para buscar pelo nome ou sobrenome do autor
autor_filtro = st.sidebar.text_input("Autor")

# Carrega as situações atuais possíveis (Tramitando, Arquivada, etc.)
situacoes_disponiveis = load_distinct_values("situacao")
situacao_filtro = st.sidebar.selectbox("Situação da Proposição", situacoes_disponiveis)

# Busca textual ampla em ementa, indexação ou descrição
keyword = st.sidebar.text_input("Palavra-chave extra (Opcional)")

st.sidebar.markdown("---")
st.sidebar.markdown("**Filtro de Período**")

# --- NOVO: Botão para escolher qual data o calendário vai filtrar ---
# Define se o período escolhido abaixo se refere ao nascimento do projeto ou ao seu último andamento
tipo_data = st.sidebar.radio(
    "Filtrar período pela:",
    ["Data de Apresentação", "Última Movimentação"]
)

# Pega a data mais antiga do banco para o limite do calendário
min_data_db = load_min_date()
data_inicio = st.sidebar.date_input("Data Início", min_data_db)
data_fim = st.sidebar.date_input("Data Fim", date.today())

# --- NOVO: Controle de Ordenação ---
# Define como a tabela principal será classificada visualmente para o usuário
st.sidebar.markdown("---")
ordenacao = st.sidebar.radio(
    "Ordenar resultados por:",
    ["Relevância da IA", "Data Mais Recente"]
)

def build_where_clause():
    """Constrói a cláusula WHERE do SQL dinamicamente baseada nos filtros ativos."""
    clausulas = []
    
    # O Python verifica o que você selecionou no botão e escolhe a coluna certa do banco
    coluna_data = "datadeapresentacao" if tipo_data == "Data de Apresentação" else "dataultimo"
    
    # Exige que a data não seja nula e esteja dentro do período do calendário
    clausulas.append(f"{coluna_data} IS NOT NULL")
    clausulas.append(f"{coluna_data} BETWEEN '{data_inicio}' AND '{data_fim}'")
    
    # Filtro com LIKE para encontrar trechos do número da norma
    if numero_norma:
        clausulas.append(f"norma LIKE '%{numero_norma}%'")
        
    # Filtro de correspondência exata para partido
    if partido_filtro != "Todos":
        clausulas.append(f"partido = '{partido_filtro}'")
        
    # Filtro com LIKE para encontrar partes do nome do autor
    if autor_filtro:
        clausulas.append(f"autor LIKE '%{autor_filtro}%'")
        
    # Filtro de correspondência exata para situação
    if situacao_filtro != "Todos":
        clausulas.append(f"situacao = '{situacao_filtro}'")
        
    # Busca complexa: olha em 3 colunas diferentes ao mesmo tempo
    if keyword:
        clausulas.append(f"""
        (ementa LIKE '%{keyword}%' 
         OR indexacao LIKE '%{keyword}%' 
         OR descricao LIKE '%{keyword}%')
        """)
        
    # Une todas as regras com 'AND' para criar o filtro final estrito
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
with tab_proposicoes:
    st.subheader("Detalhamento dos Projetos")

    # --- NOVA LÓGICA DE ORDENAÇÃO DINÂMICA COM O NOVO BOTÃO ---
    if ordenacao == "Relevância da IA":
        # Se escolheu a IA, a nota de relevância manda em tudo (do maior pro menor)
        ordem_sql = "ORDER BY score_relevancia DESC"
    else:
        # Se escolheu "Data Mais Recente", o Python olha pro filtro de cima para saber qual data usar como prioridade
        if tipo_data == "Data de Apresentação":
            # Ordena primeiro pelo nascimento mais recente, e usa a nota da IA para desempatar projetos do mesmo dia
            ordem_sql = "ORDER BY datadeapresentacao DESC, score_relevancia DESC"
        else:
            # Ordena primeiro pela movimentação mais recente, e usa a nota da IA para desempatar
            ordem_sql = "ORDER BY dataultimo DESC, score_relevancia DESC"

# Aqui ocorre a união do filtro de pesquisa com a ordem escolhida pelo usuário
    query_props = f"""
    SELECT
        score_relevancia as "Relevância (IA)",
        norma as "Norma",
        autor as "Autor",
        partido as "Partido",
        situacao as "Situação",
        datadeapresentacao as "Data Apresentação",  
        dataultimo as "Última Movimentação",        
        ultimoestado as "Descrição do Andamento",   -- NOVA COLUNA ADICIONADA AQUI!
        ementa as "Ementa",
        linkweb as "Link"
    FROM Projetos
    {build_where_clause()}
    {ordem_sql}  -- O comando final de ordem entra aqui!
    """
    
    # Chama a função principal de conexão e converte o resultado em um dataframe pandas
    df_props = load_data(query_props)

    if df_props.empty:
        st.warning("Nenhuma proposição encontrada com esses filtros.")
    else:
        # Renderiza a tabela do Streamlit formatando o link para ser clicável
        st.dataframe(
            df_props,
            column_config={
                "Link": st.column_config.LinkColumn("Link da Câmara")
            },
            use_container_width=True,
            hide_index=True
        )