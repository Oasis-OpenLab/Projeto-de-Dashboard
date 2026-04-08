import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import date
import config

import glob
import json
import os

# --- NOVOS IMPORTS PARA O MOTOR FUNCIONAR NO PAINEL ---
from sentence_transformers import SentenceTransformer
import filtrador_hibrido_v3_final as motor_ia
import insert_data as motor_banco

def rodar_dashboard():
    # ==============================================
    # 2) CONEXÃO E FUNÇÕES AUXILIARES
    # ==============================================

    @st.cache_data
    def load_data(query):
        conn = mysql.connector.connect(
            host=config.HOST,
            user=config.USUARIO,
            password=config.SENHA,
            database=config.NOME,
            port = config.porta,
            ssl_ca = config.certificado
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
    # 3) INICIALIZAÇÃO DO MOTOR DE BUSCA
    # ==============================================
    # Congela o modelo na memória RAM para as pesquisas serem instantâneas
    @st.cache_resource
    def carregar_modelo_ia():
        return SentenceTransformer(config.MODELO_NOME, device=config.dispositivo)

    modelo_nlp = carregar_modelo_ia()

    with open( 'banco_de_dados_local/pesquisa1.txt', 'r', encoding='utf-8') as arquivo:
        tema_pesquisa_principal = arquivo.readline()
        arquivo.close()
    with open( 'banco_de_dados_local/pesquisa2.txt', 'r', encoding='utf-8') as arquivo:
        tema_pesquisa_secundaria = arquivo.readline()
        arquivo.close()

    # 1. Manda o texto e o modelo congelado para o filtrador
    motor_ia.executar_filtragem(tema_pesquisa_principal, tema_pesquisa_secundaria, modelo_nlp)
            
    # 2. Manda o insert_data apagar a tabela velha e salvar a nova
    motor_banco.atualizar_banco_sql()
            
    # ==============================================
    # 5) SIDEBAR — FILTROS DO PAINEL
    # ==============================================
    st.sidebar.header("⚙️ Filtros do Painel")

    # Filtro de texto para buscar pelo número exato ou parcial da norma (ex: PL 2338/2023 ou 2338)
    numero_norma = st.sidebar.text_input("Norma",  help="Permite buscar pelo número total ou parcial da proposição. Ex: 'PL 2338/2023' ou apenas '2338'.")

    # Carrega opções dinâmicas de partidos direto do banco de dados
    partidos_disponiveis = load_distinct_values("partido")
    partido_filtro = st.sidebar.selectbox("Partido do Autor", partidos_disponiveis, help="Filtra projetos de lei de acordo com o partido do autor principal da proposição.")

    # Filtro de texto para buscar pelo nome ou sobrenome do autor
    autor_filtro = st.sidebar.text_input("Autor", help="Busca projetos pelo nome ou sobrenome do autor da proposição.")

    # Carrega as situações atuais possíveis (Tramitando, Arquivada, etc.)
    situacoes_disponiveis = load_distinct_values("situacao")
    situacao_filtro = st.sidebar.selectbox("Situação da Proposição", situacoes_disponiveis, help="Mostra apenas projetos que estejam na situação selecionada (ex: Tramitando, Arquivado, Aprovado).")

    # Busca textual ampla em ementa, indexação ou descrição
    keyword = st.sidebar.text_input("Palavra-chave extra (Opcional)", help="Busca termos específicos dentro da ementa, indexação e descrição técnica do projeto.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Filtro de Período**")

    # Define se o período escolhido abaixo se refere ao nascimento do projeto ou ao seu último andamento
    tipo_data = st.sidebar.radio(
        "Filtrar período pela:",
        ["Data de Apresentação", "Última Movimentação"],
        help="Define se o período selecionado considera a criação do projeto ou sua última atualização na Câmara."
    )

    # Pega a data mais antiga do banco para o limite do calendário
    min_data_db = load_min_date()
    data_inicio = st.sidebar.date_input("Data Início", min_data_db, help="Mostra apenas projetos a partir desta data.")
    data_fim = st.sidebar.date_input("Data Fim", date.today(), help="Mostra apenas projetos até esta data.")

    # Define como a tabela principal será classificada visualmente para o usuário
    st.sidebar.markdown("---")
    ordenacao = st.sidebar.radio(
        "Ordenar resultados por:",
        ["Relevância de Score", "Data Mais Recente"],
        help="Relevância da IA ordena pelos projetos mais alinhados ao tema analisado. Data Mais Recente mostra os projetos mais novos primeiro."
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
    # 6) ESTRUTURA DE ABAS
    # ==============================================
    tab_visao, tab_proposicoes, tab_busca_global = st.tabs([
        "📊 Visão Geral", 
        "📄 Lista Filtrada", 
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
            col1.metric("Total de Projetos Filtrados", total_projetos)
            col2.metric("Partidos Envolvidos", total_partidos)

            st.markdown("---")
            # -------------------------------
            # Gráfico: Projetos por ano
            # -------------------------------
            query = f"""
                    SELECT YEAR(datadeapresentacao) AS ano, COUNT(*) AS quantidade
                    FROM Projetos
                    {build_where_clause()}
                    GROUP BY YEAR(datadeapresentacao)
                    ORDER BY ano;
                    """
            df = load_data(query)
            fig = px.line(
                df,
                x="ano",
                y="quantidade",
                title = "Projetos por ano",
                markers = True
            )
            fig.update_xaxes(dtick=1)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            # -------------------------------
            # Gráfico: Distribuição de Projetos por Partido
            # -------------------------------
            query = f"""
            SELECT partido, COUNT(*) AS quantidade
            FROM Projetos
            {build_where_clause()}
            AND partido IS NOT NULL AND partido <> ''
            GROUP BY partido
            ORDER BY quantidade DESC;
            """
            df = load_data(query)
            fig = px.treemap(
                df,
                path=[px.Constant("Todos os Partidos"), "partido"],  # Define a hierarquia
                values="quantidade",
                color="quantidade",
                color_continuous_scale="Ice",
                title="Distribuição de Projetos por Partido"
            )
            # Ajustes estéticos para exibir os rótulos corretamente
            fig.update_traces(textinfo="label+value")
            fig.update_layout(height=600, margin=dict(t=50, l=10, r=10, b=10))

            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            col_graf1, col_graf2 = st.columns(2)

            with col_graf1:
                # -------------------------------
                # Gráfico: Top 10 Partidos com Mais Projetos
                # -------------------------------
                df_partido = df_visao.groupby('partido', as_index=False)['quantidade'].sum().reset_index()
                df_partido = df_partido.sort_values(by='quantidade', ascending=False).head(10)
                fig1 = px.bar(
                    df_partido,
                    x="partido",
                    y="quantidade",
                    title="Top 10 Partidos com Mais Projetos",
                    labels={"partido": "Partido", "quantidade": "Projetos"}
                )
                st.plotly_chart(fig1, use_container_width=True)

            with col_graf2:
                # -------------------------------
                # Gráfico: Distribuição por Situação Atual
                # -------------------------------
                # 1. Agrupa por situacao e soma a coluna quantidade
                df_sit = df_visao.groupby('situacao')['quantidade'].sum().reset_index()
                # 2. Agora ordena (fora do agrupamento para não dar erro de argumento)
                df_sit = df_sit.sort_values(by="quantidade", ascending=True)

                fig2 = px.bar(
                    df_sit,
                    x="quantidade",
                    y="situacao",
                    orientation="h",
                    text="quantidade",  # Mostra o número exato na ponta da barra
                    title="Projetos por Situação Atual",
                    # Mesma lógica de cor: Degradê do Laranja para o Azul
                    color="quantidade",
                    color_continuous_scale=["#118AB2", "#FF9F1C"]
                )

                fig2.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=50, t=50, b=10),  # Margem lateral para o texto da esquerda não cortar
                    height=400,
                    showlegend=False
                )

                fig2.update_traces(
                    textposition='outside',  # Valor numérico fora da barra
                    marker=dict(line=dict(width=1, color="#073B4C")),
                    cliponaxis=False  # Garante que o número na ponta da barra não seja cortado
                )

                # Remove as grades do fundo para um look mais limpo
                fig2.update_xaxes(showgrid=False, visible=False)
                fig2.update_yaxes(showgrid=False, title="")

                st.plotly_chart(fig2, use_container_width=True)
        st.markdown("---")

        # -------------------------------
        # Gráficos: Distribuição de Projetos por Espectro Político
        # -------------------------------
        st.markdown("**Distribuição de Projetos por Espectro Político**")
        st.caption("Fonte da Classificação Partidária: Jornal Valor Econômico")
        tab_esp_tree, tab_esp_bar = st.tabs([
            "Mapa de Árvore", 
            "Gráfico de Barra", 
        ])

        mapa_espectro = {
            "AGIR": "Centro-Direita",
            "AVANTE": "Centro",
            "CIDADANIA": "Centro-Esquerda",
            "DC": "Visão Independente",
            "DEM": "Centro-Direita",
            "MDB": "Centro",
            "MOBILIZA": "Centro-Direita",
            "NOVO": "Direita",
            "PATRI": "Extrema-Direita",
            "PCB": "Esquerda",
            "PCdoB": "Esquerda",
            "PCO": "Extrema-Esquerda",
            "PDT": "Centro-Esquerda",
            "PL": "Direita",
            "PMB": "Centro",
            "PODE": "Visão Independente",
            "PP": "Centro-Direita",
            "PPS": "Centro-Esquerda",
            "PR": "Direita",
            "PRB": "Centro-Direita",
            "PRD": "Centro-Direita",
            "PROS": "Centro",
            "PRTB": "Direita",
            "PSB": "Centro-Esquerda",
            "PSC": "Direita",
            "PSD": "Centro",
            "PSDB": "Centro",
            "PSL": "Direita",
            "PSOL": "Esquerda",
            "PSTU": "Esquerda",
            "PT": "Esquerda",
            "PTB": "Direita",
            "PV": "Centro-Esquerda",
            "REDE": "Esquerda",
            "REPUBLICANOS": "Direita",
            "SOLIDARIEDADE": "Centro",
            "UNIÃO": "Centro-Direita",
            "UP": "Esquerda"
        }
        cores={
            "Não Atribuído": "#E0E0E0",
            "Extrema-Esquerda": "#C97A7A",
            "Esquerda": "#E89A9A",
            "Centro-Esquerda": "#F2B6B6",
            "Centro": "#C8B6C8",
            "Centro-Direita": "#B6C3F2",
            "Direita": "#8FA8E8",
            "Extrema-Direita": "#6F88C9",
            "Visão Independente": "#A0A0A0" 
        }

        query = f"""
        SELECT partido, COUNT(*) AS quantidade
        FROM Projetos
        {build_where_clause()}
        AND partido IS NOT NULL AND partido <> ''
        GROUP BY partido
        ORDER BY quantidade DESC;
        """
        df = load_data(query)
        df['espectro']= df['partido'].map(mapa_espectro).fillna("Não Atribuído")
        
        with tab_esp_tree:
            fig = px.treemap(
                df,
                path=[px.Constant("Todos os Espectros"),"espectro", "partido"],
                values="quantidade",
                color="espectro",
                color_discrete_map=cores
            )
            fig.update_traces(
                textinfo="label+value",
                textfont=dict(color="black")
            )
            st.plotly_chart(fig, use_container_width=True)
        
        df_agg = df.groupby("espectro")["quantidade"].sum().reset_index()
        df_agg = df_agg.sort_values("quantidade", ascending=False)
        
        with tab_esp_bar:
            fig = px.bar(
                df_agg,
                x="espectro",
                y="quantidade",
                labels={"espectro": "Espectro Político", "quantidade": "Projetos"},
                color="espectro",
                color_discrete_map=cores
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- ABA 2: PROPOSIÇÕES ---
    with tab_proposicoes:
        st.subheader("Detalhamento dos Projetos")

        if ordenacao == "Relevância de Score":
            ordem_sql = "ORDER BY score_relevancia DESC"
        else:
            if tipo_data == "Data de Apresentação":
                ordem_sql = "ORDER BY datadeapresentacao DESC, score_relevancia DESC"
            else:
                ordem_sql = "ORDER BY dataultimo DESC, score_relevancia DESC"

        # UNIÃO DO FILTRO DE PESQUISA COM A ORDEM ESCOLHIDA
        query_props = f"""
        SELECT
            score_relevancia as "Relevância (Score)",
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
        st.subheader("🌐 Busca na Base Completa da Câmara")
        st.markdown("Pesquise em **todos** os projetos coletados.")
        
        busca_livre = st.text_input("🔍 Digite o número da norma (Ex: PL 2338/2023) ou uma palavra-chave para buscar na base inteira:", help="Pesquisa direta em todos os projetos coletados da Câmara, inclusive os que não passaram pelo filtro da IA.")
        
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
                    
                    # CRUZAMENTO COM O BANCO DE DADOS (SCORE)
                    if not df_resultado.empty:
                        try:
                            # Tenta buscar as notas do banco de dados MySQL
                            df_notas = load_data("SELECT norma, score_relevancia FROM Projetos")
                            
                            # Cruza a tabela bruta com a tabela de notas
                            df_resultado = df_resultado.merge(df_notas, left_on='Norma', right_on='norma', how='left')
                            
                            # Define o que escrever na coluna de Score
                            df_resultado['Score'] = df_resultado['score_relevancia'].apply(
                                lambda x: f"{float(x):.4f}" if pd.notnull(x) else "Abaixo da nota de corte (< 0.40)"
                            )
                            
                            # Limpa colunas auxiliares do cruzamento
                            df_resultado = df_resultado.drop(columns=['norma', 'score_relevancia'])
                            
                        except Exception as e:
                            df_resultado['Score'] = "⚠️ Pendente: Rode o main.py"
                        
                        colunas_ordenadas = ['Norma', 'Score', 'Data de Apresentação', 'Autor', 'Situação', 'Ementa', 'Link']
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