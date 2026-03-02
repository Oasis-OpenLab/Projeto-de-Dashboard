import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import date
import config

import glob
import json
import os

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

@st.cache_data
def load_base_completa():
    """Lê todos os JSONs brutos da Câmara e transforma num DataFrame para busca rápida."""
    padrao = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
    arquivos = glob.glob(padrao)
    
    dados_completos = []
    for arquivo in arquivos:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                for p in dados:
                    # Monta o número da norma (ex: PL 123/2023)
                    norma = f"{p.get('siglaTipo', '')} {p.get('numero', '')}/{p.get('ano', '')}"
                    
                    # Pega a situação atual de forma segura
                    status = p.get('statusProposicao', {})
                    if not isinstance(status, dict): status = {}
                    
                    dados_completos.append({
                        "Norma": norma,
                        "Data de Apresentação": p.get('dataApresentacao', '')[:10] if p.get('dataApresentacao') else '',
                        "Autor": p.get('autor_principal_nome', 'Desconhecido'),
                        "Situação": status.get('descricaoSituacao', 'Desconhecida'),
                        "Ementa": p.get('ementa', ''),
                        "Link": p.get('url_pagina_web_oficial', '')
                    })
                    
    # Converte para DataFrame do Pandas para facilitar a tabela
    return pd.DataFrame(dados_completos)

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

# Define se o período escolhido abaixo se refere ao nascimento do projeto ou ao seu último andamento
tipo_data = st.sidebar.radio(
    "Filtrar período pela:",
    ["Data de Apresentação", "Última Movimentação"]
)

# Pega a data mais antiga do banco para o limite do calendário
min_data_db = load_min_date()
data_inicio = st.sidebar.date_input("Data Início", min_data_db)
data_fim = st.sidebar.date_input("Data Fim", date.today())

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
    
    if numero_norma:
        clausulas.append(f"norma LIKE '%{numero_norma}%'")
        
    if partido_filtro != "Todos":
        clausulas.append(f"partido = '{partido_filtro}'")
        
    if autor_filtro:
        clausulas.append(f"autor LIKE '%{autor_filtro}%'")
        
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
tab_visao, tab_proposicoes, tab_busca_global = st.tabs([
    "📊 Visão Geral", 
    "📄 Lista Filtrada (IA)", 
    "🌐 Busca Global (Base Completa)"
])

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

    # LÓGICA DE ORDENAÇÃO DINÂMICA
    if ordenacao == "Relevância da IA":
        ordem_sql = "ORDER BY score_relevancia DESC"
    else:
        if tipo_data == "Data de Apresentação":
            ordem_sql = "ORDER BY datadeapresentacao DESC, score_relevancia DESC"
        else:
            ordem_sql = "ORDER BY dataultimo DESC, score_relevancia DESC"

    # UNIÃO DO FILTRO DE PESQUISA COM A ORDEM ESCOLHIDA
    query_props = f"""
    SELECT
        score_relevancia as "Relevância (IA)",
        norma as "Norma",
        autor as "Autor",
        partido as "Partido",
        situacao as "Situação",
        datadeapresentacao as "Data Apresentação",  
        dataultimo as "Última Movimentação",        
        ultimoestado as "Descrição do Andamento",   
        ementa as "Ementa",
        linkweb as "Link"
    FROM Projetos
    {build_where_clause()}
    {ordem_sql}
    """
    
    df_props = load_data(query_props)

    if df_props.empty:
        st.warning("Nenhuma proposição encontrada com esses filtros.")
    else:
        st.dataframe(
            df_props,
            column_config={
                "Link": st.column_config.LinkColumn("Link da Câmara")
            },
            use_container_width=True,
            hide_index=True
        )

# --- ABA 3: BUSCA GLOBAL (BASE COMPLETA) ---
with tab_busca_global:
    st.subheader("🌐 Busca na Base Completa da Câmara (Sem Filtro de IA)")
    st.markdown("Pesquise em **todos** os projetos coletados. Se o projeto tiver passado pelo funil da IA, a nota aparecerá ao lado.")
    
    busca_livre = st.text_input("🔍 Digite o número da norma (Ex: PL 2338/2023) ou uma palavra-chave para buscar na base inteira:")
    
    if busca_livre:
        with st.spinner("Buscando nos arquivos locais e cruzando com o banco de dados..."):
            df_completo = load_base_completa()
            
            if not df_completo.empty:
                termo = busca_livre.lower()
                
                # Filtra a base bruta
                mask = (
                    df_completo['Norma'].str.lower().str.contains(termo, na=False) |
                    df_completo['Ementa'].str.lower().str.contains(termo, na=False) |
                    df_completo['Autor'].str.lower().str.contains(termo, na=False)
                )
                df_resultado = df_completo[mask].copy()
                
                # CRUZAMENTO COM O BANCO DE DADOS (SCORE IA)
                if not df_resultado.empty:
                    try:
                        # Tenta buscar as notas do banco de dados MySQL
                        df_notas = load_data("SELECT norma, score_relevancia FROM Projetos")
                        
                        # Cruza a tabela bruta com a tabela de notas
                        df_resultado = df_resultado.merge(df_notas, left_on='Norma', right_on='norma', how='left')
                        
                        # Define o que escrever na coluna de Score
                        df_resultado['Score IA'] = df_resultado['score_relevancia'].apply(
                            lambda x: f"{float(x):.4f}" if pd.notnull(x) else "Barrado pela IA (< 0.40)"
                        )
                        
                        # Limpa colunas auxiliares do cruzamento
                        df_resultado = df_resultado.drop(columns=['norma', 'score_relevancia'])
                        
                    except Exception as e:
                        # Se der erro, significa que o MySQL ainda não tem a coluna de notas
                        df_resultado['Score IA'] = "⚠️ Pendente: Rode o main.py"
                    
                    # Organiza a ordem das colunas para a nota ficar logo no começo
                    colunas_ordenadas = ['Norma', 'Score IA', 'Data de Apresentação', 'Autor', 'Situação', 'Ementa', 'Link']
                    colunas_finais = [c for c in colunas_ordenadas if c in df_resultado.columns]
                    df_resultado = df_resultado[colunas_finais]

                st.success(f"Foram encontrados **{len(df_resultado)}** projetos na base completa.")
                
                st.dataframe(
                    df_resultado,
                    column_config={"Link": st.column_config.LinkColumn("Link da Câmara")},
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.error("Nenhum dado bruto encontrado. Verifique se os arquivos JSON foram gerados.")
    else:
        st.info("Digite algo na barra de pesquisa acima para carregar os projetos.")