import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import config

import mysql.connector

import glob
import json
import os

import gzip

def rodar_dashboard():
    # ==============================================
    # 2) CONEXÃO E FUNÇÕES AUXILIARES (PANDAS ONLY)
    # ==============================================

    @st.cache_data
    def load_data():
        """Lê o arquivo CSV processado localmente."""
        csv_file_path = os.path.join("projetos_em_csv", "proposicoes_camara_resumo.csv")
        if os.path.exists(csv_file_path):
            df = pd.read_csv(csv_file_path, delimiter=";")
            # Padroniza nomes das colunas para minúsculo sem espaços
            df.columns = [str(c).lower().replace(" ", "").replace("ç", "c").replace("ã", "a").replace("á", "a").replace("ú", "u") for c in df.columns]
            return df
        return pd.DataFrame()

    df_csv_completo = load_data()

    @st.cache_data
    def load_distinct_values(coluna):
        """Busca os valores únicos direto do DataFrame Pandas."""
        if not df_csv_completo.empty and coluna in df_csv_completo.columns:
            valores = df_csv_completo[coluna].dropna().unique().tolist()
            return ["Todos"] + sorted(valores)
        return ["Todos"]

    @st.cache_data
    def load_min_date():
        """Busca a menor data direto do DataFrame Pandas."""
        if not df_csv_completo.empty and 'datadeapresentacao' in df_csv_completo.columns:
            min_val = pd.to_datetime(df_csv_completo['datadeapresentacao'], errors='coerce').min()
            if pd.notnull(min_val):
                return min_val.date()
        return date(2000, 1, 1)

    @st.cache_data
    def load_base_completa():
        """Lê todos os JSONs brutos da Câmara."""
        padrao = os.path.join(config.PASTA_DADOS, "camara_db_leg*.json")
        arquivos = glob.glob(padrao)
        dados_completos = []
        for arquivo in arquivos:
            if os.path.exists(arquivo):
                with open(arquivo, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                    for p in dados:
                        norma = f"{p.get('siglaTipo', '')} {p.get('numero', '')}/{p.get('ano', '')}"
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
        return pd.DataFrame(dados_completos)
    
    #@st.cache_data(ttl=300) # Cache de 5 minutos para não travar o banco
    def buscar_tramitacoes_banco(norma):
        norma_limpa = str(norma).upper().strip()
        df = pd.DataFrame()
        
        # Lê o histórico direto do JSON (INFALÍVEL E RÁPIDO)
        try:
            caminho_cache = os.path.join(config.PASTA_DADOS, "camara_tramitacoes_cache.json.gz")
            if os.path.exists(caminho_cache):
                with gzip.open(caminho_cache, 'rt', encoding='utf-8') as f:
                    cache_json = json.load(f)
                if norma_limpa in cache_json:
                    df = pd.DataFrame(cache_json[norma_limpa])
                    if not df.empty:
                        df = df.sort_values(by='sequencia', ascending=False)
        except Exception as e:
            print(f"Erro ao ler JSON GZIP: {e}")
                
        return df
            
    # ==============================================
    # 5) SIDEBAR — FILTROS DO PAINEL
    # ==============================================
    st.sidebar.header("⚙️ Filtros do Painel")

    numero_norma = st.sidebar.text_input("Norma",  help="Permite buscar pelo número total ou parcial.")
    
    partidos_disponiveis = load_distinct_values("partido")
    partido_filtro = st.sidebar.selectbox("Partido do Autor", partidos_disponiveis)

    autor_filtro = st.sidebar.text_input("Autor")

    situacoes_disponiveis = load_distinct_values("situacao")
    situacao_filtro = st.sidebar.selectbox("Situação da Proposição", situacoes_disponiveis)

    keyword = st.sidebar.text_input("Palavra-chave extra (Opcional)")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Filtro de Período**")

    tipo_data = st.sidebar.radio("Filtrar período pela:", ["Data de Apresentação", "Última Movimentação"])

    min_data_db = load_min_date()
    data_inicio = st.sidebar.date_input("Data Início", min_data_db)
    data_fim = st.sidebar.date_input("Data Fim", date.today())

    st.sidebar.markdown("---")
    ordenacao = st.sidebar.radio("Ordenar resultados por:", ["Relevância de Score", "Data Mais Recente"])

    def filtrar_dataframe_via_pandas():
        """Aplica os filtros da Sidebar diretamente no CSV sem usar Banco de Dados."""
        if df_csv_completo.empty:
            return df_csv_completo
        df = df_csv_completo.copy()
        
        # Filtro Data
        coluna_data = "datadeapresentacao" if tipo_data == "Data de Apresentação" else "dataultimoestado"
        if coluna_data in df.columns:
            df[coluna_data] = pd.to_datetime(df[coluna_data], errors='coerce').dt.date
            df = df[(df[coluna_data] >= data_inicio) & (df[coluna_data] <= data_fim)]

        # Filtros texto e selects
        if numero_norma and 'norma' in df.columns:
            df = df[df['norma'].astype(str).str.contains(numero_norma, case=False, na=False)]
        if partido_filtro != "Todos" and 'partido' in df.columns:
            df = df[df['partido'] == partido_filtro]
        if autor_filtro and 'autor' in df.columns:
            df = df[df['autor'].astype(str).str.contains(autor_filtro, case=False, na=False)]
        if situacao_filtro != "Todos" and 'situacao' in df.columns:
            df = df[df['situacao'] == situacao_filtro]
        
        # Filtro palavra-chave (ementa, indexacao, descricao)
        if keyword:
            mask = pd.Series(False, index=df.index)
            for col in ['ementa', 'indexacao', 'descricao']:
                if col in df.columns:
                    mask = mask | df[col].astype(str).str.contains(keyword, case=False, na=False)
            df = df[mask]
            
        return df

    # ==============================================
    # 6) ESTRUTURA DE ABAS
    # ==============================================
    tab_visao, tab_proposicoes, tab_busca_global = st.tabs([
        "📊 Visão Geral", 
        "📄 Lista Filtrada", 
        "🌐 Busca Global"
    ])

    # --- ABA 1: VISÃO GERAL ---
    with tab_visao:
        st.subheader("Métricas do Tema Filtrado")

        df_visao = filtrar_dataframe_via_pandas()

        if df_visao.empty:
            st.warning("Nenhum dado encontrado com os filtros atuais.")
        else:
            total_projetos = len(df_visao)
            total_partidos = df_visao['partido'].nunique() if 'partido' in df_visao.columns else 0
            
            col1, col2 = st.columns(2)
            col1.metric("Total de Projetos Filtrados", total_projetos)
            col2.metric("Partidos Envolvidos", total_partidos)
            st.markdown("---")

            # Gráfico: Projetos por ano
            if 'datadeapresentacao' in df_visao.columns:
                df_ano = df_visao.copy()
                df_ano['ano'] = pd.to_datetime(df_ano['datadeapresentacao'], errors='coerce').dt.year
                df_ano_contagem = df_ano.groupby('ano').size().reset_index(name='quantidade')
                fig = px.line(df_ano_contagem, x="ano", y="quantidade", title="Projetos por ano", markers=True)
                st.plotly_chart(fig, width='stretch')
                st.markdown("---")
            
            if 'partido' in df_visao.columns:
                # Gráfico: Treemap
                df_partido_tree = df_visao[df_visao['partido'].notnull() & (df_visao['partido'] != '')]
                df_partido_tree_contagem = df_partido_tree.groupby('partido').size().reset_index(name='quantidade').sort_values(by='quantidade', ascending=False)

                tab_part_tree, tab_part_bar = st.tabs(["Mapa de Árvore", "Gráfico de Barra"])

                with tab_part_tree:
                    fig = px.treemap(df_partido_tree_contagem, path=[px.Constant("Todos os Partidos"), "partido"], values="quantidade", color="quantidade", color_continuous_scale="Ice", title="Distribuição de Projetos por Partido")
                    fig.update_traces(textinfo="label+value")
                    st.plotly_chart(fig, width='stretch')

                with tab_part_bar:
                    fig = px.bar(df_partido_tree_contagem, y="partido", x="quantidade", orientation="h",
                                 title="Distribuição de Projetos por Partido", color="quantidade",
                                 color_continuous_scale="Ice", text="quantidade")
                    fig.update_traces(textposition='outside')
                    fig.update_xaxes(visible=False)
                    fig.update_yaxes(title="")
                    st.plotly_chart(fig, width='stretch')

                st.markdown("---")

                col_graf1, col_graf2 = st.columns(2)
                with col_graf1:
                    df_top_partidos = df_partido_tree_contagem.head(10)
                    fig1 = px.bar(df_top_partidos, x="partido", y="quantidade", title="Top 10 Partidos")
                    st.plotly_chart(fig1, width='stretch')

                with col_graf2:
                    if 'situacao' in df_visao.columns:
                        df_sit_contagem = df_visao.groupby('situacao').size().reset_index(name='quantidade').sort_values(by="quantidade", ascending=True)
                        fig2 = px.bar(df_sit_contagem, x="quantidade", y="situacao", orientation="h", title="Projetos por Situação", text="quantidade")
                        fig2.update_traces(textposition='outside')
                        fig2.update_xaxes(visible=False)
                        fig2.update_yaxes(title="")
                        st.plotly_chart(fig2, width='stretch')

        st.markdown("---")
        st.markdown("**Distribuição de Projetos por Espectro Político**")
        
        mapa_espectro = {"AGIR": "Centro-Direita", "AVANTE": "Centro", "CIDADANIA": "Centro-Esquerda", "DC": "Visão Independente", "DEM": "Centro-Direita", "MDB": "Centro", "MOBILIZA": "Centro-Direita", "NOVO": "Direita", "PATRI": "Extrema-Direita", "PCB": "Esquerda", "PCdoB": "Esquerda", "PCO": "Extrema-Esquerda", "PDT": "Centro-Esquerda", "PL": "Direita", "PMB": "Centro", "PODE": "Visão Independente", "PP": "Centro-Direita", "PPS": "Centro-Esquerda", "PR": "Direita", "PRB": "Centro-Direita", "PRD": "Centro-Direita", "PROS": "Centro", "PRTB": "Direita", "PSB": "Centro-Esquerda", "PSC": "Direita", "PSD": "Centro", "PSDB": "Centro", "PSL": "Direita", "PSOL": "Esquerda", "PSTU": "Esquerda", "PT": "Esquerda", "PTB": "Direita", "PV": "Centro-Esquerda", "REDE": "Esquerda", "REPUBLICANOS": "Direita", "SOLIDARIEDADE": "Centro", "UNIÃO": "Centro-Direita", "UP": "Esquerda"}
        cores={"Não Atribuído": "#E0E0E0", "Extrema-Esquerda": "#C97A7A", "Esquerda": "#E89A9A", "Centro-Esquerda": "#F2B6B6", "Centro": "#C8B6C8", "Centro-Direita": "#B6C3F2", "Direita": "#8FA8E8", "Extrema-Direita": "#6F88C9", "Visão Independente": "#A0A0A0"}

        if not df_visao.empty and 'partido' in df_visao.columns:
            df_esp = df_visao[df_visao['partido'].notnull() & (df_visao['partido'] != '')].groupby('partido').size().reset_index(name='quantidade')
            df_esp['espectro'] = df_esp['partido'].map(mapa_espectro).fillna("Não Atribuído")
            
            tab_esp_tree, tab_esp_bar = st.tabs(["Mapa de Árvore", "Gráfico de Barra"])
            with tab_esp_tree:
                fig = px.treemap(df_esp, path=[px.Constant("Todos os Espectros"),"espectro", "partido"], values="quantidade", color="espectro", color_discrete_map=cores)
                st.plotly_chart(fig, width='stretch')
            with tab_esp_bar:
                df_agg = df_esp.groupby("espectro")["quantidade"].sum().reset_index().sort_values("quantidade", ascending=False)
                fig = px.bar(df_agg, x="espectro", y="quantidade", color="espectro", color_discrete_map=cores)
                st.plotly_chart(fig, width='stretch')

    # --- ABA 2: PROPOSIÇÕES ---
    with tab_proposicoes:
        st.subheader("Detalhamento dos Projetos")
        
        df_props_filtrado = filtrar_dataframe_via_pandas()

        if df_props_filtrado.empty:
            st.warning("Nenhuma proposição encontrada com esses filtros.")
        else:
            if ordenacao == "Relevância de Score" and 'scorefinal' in df_props_filtrado.columns:
                df_props_filtrado = df_props_filtrado.sort_values(by='scorefinal', ascending=False)
            elif tipo_data == "Data de Apresentação" and 'datadeapresentacao' in df_props_filtrado.columns:
                df_props_filtrado = df_props_filtrado.sort_values(by=['datadeapresentacao'], ascending=[False])
            elif 'dataultimoestado' in df_props_filtrado.columns:
                df_props_filtrado = df_props_filtrado.sort_values(by=['dataultimoestado'], ascending=[False])

            renomear = {
                "idproposicao": "ID", 
                "scorefinal": "Relevância (Score)", 
                "norma": "Norma", 
                "autor": "Autor",
                "partido": "Partido", 
                "ementa": "Ementa",
                "situacao": "Situação", 
                "datadeapresentacao": "Data Apresentação",
                "dataultimoestado": "Última Movimentação", 
                "ultimoestado": "Descrição do Andamento",
                "linkpaginaweb": "Link", 
                "linkdocumentopdf": "Documento PDF"
            }
            df_exibicao = df_props_filtrado.rename(columns=renomear)
            colunas_mostrar = [c for c in renomear.values() if c in df_exibicao.columns]
            df_exibicao = df_exibicao[colunas_mostrar]

            @st.dialog("Histórico de Tramitação", width="large")
            def mostrar_modal_tramitacao_aba2(linha):
                st.markdown(f"### 📑 {linha.get('Norma', '')}")
                st.markdown(f"### **Autor:** {linha.get('Autor', '')} - {linha.get('Partido', '')}")
                st.caption(f"**Ementa:** {linha.get('Ementa', '')}")
                st.markdown("---")
                st.markdown("#### 📍 Situação Atual")
                st.info(f"**{linha.get('Situação', '')}** — {linha.get('Descrição do Andamento', '')}")
                st.markdown("---")
                st.markdown("#### 🔗 Documentos e Links Oficiais")
                c1, c2 = st.columns(2)
                id_prop = str(linha.get('ID', '')).replace('.0', '').strip()
                
                if id_prop and id_prop.lower() not in ['nan', 'none', '']:
                    link_web = f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={id_prop}"
                else:
                    link_web = str(linha.get('Link', '#')).strip()
                    if link_web != '#' and not link_web.startswith('http'):
                        link_web = 'https://' + link_web

                link_pdf = str(linha.get('Documento PDF', '')).strip()
                if link_pdf.lower() in ['nan', 'none', '', '#']:
                    link_pdf = "https://www.camara.leg.br"
                elif not link_pdf.startswith('http'):
                    link_pdf = 'https://' + link_pdf

                with c1: st.link_button("🌐 Página do Projeto", link_web, width='stretch')
                with c2: st.link_button("📄 Íntegra (PDF)", link_pdf, width='stretch')
                st.markdown("---")
                
                st.markdown("#### 🕒 Histórico de Movimentações")
                df_tram = buscar_tramitacoes_banco(str(linha['Norma']).strip())
                
                if not df_tram.empty:
                    for i, row in df_tram.iterrows():
                        data_t = row.get('data_tramitacao')
                        if pd.notnull(data_t):
                            data_formatada = pd.to_datetime(data_t).strftime('%d/%m/%Y')
                        else:
                            data_formatada = "Data não informada"
                            
                        orgao_t = row.get('orgao', 'Órgão não especificado')
                        desc_t = row.get('descricao_tramitacao', 'Sem descrição')
                        
                        sit_t = row.get('situacao_tramitacao', '')
                        aprec_t = row.get('apreciacao', '')
                        desp_t = row.get('despacho', '')
                        
                        texto_principal = str(desc_t)
                        if pd.notnull(sit_t) and str(sit_t).strip() and str(sit_t).lower() not in ['nan', 'none', '']:
                            texto_principal += f" — {sit_t}"
                            
                        st.markdown(f"**🟢 {data_formatada} - {orgao_t}**\n└ *{texto_principal}*")
                        
                        if pd.notnull(aprec_t) and str(aprec_t).strip() and str(aprec_t).lower() not in ['nan', 'none', '']:
                            st.markdown(f"<div style='padding-left: 20px; font-size: 0.9em;'><b>Apreciação:</b> {aprec_t}</div>", unsafe_allow_html=True)
                            
                        if pd.notnull(desp_t) and str(desp_t).strip() and str(desp_t).lower() not in ['nan', 'none', '']:
                            st.markdown(f"<div style='padding-left: 20px; font-size: 0.9em;'><b>Despacho:</b> {desp_t}</div>", unsafe_allow_html=True)
                        
                        if i < len(df_tram) - 1:
                            st.markdown("<div style='padding-left: 20px; border-left: 2px dashed #118AB2; margin: 5px 0; height: 20px;'></div>", unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Histórico detalhado não sincronizado na base. Exibindo resumo rápido do CSV:")
                    st.markdown(f"**🟢 {linha.get('Última Movimentação', 'Data não informada')}**\n└ *{linha.get('Descrição do Andamento', 'Sem descrição de andamento')}*")
                    st.markdown("<div style='padding-left: 20px; border-left: 2px dashed #118AB2; margin: 10px 0;'>Tramitação em andamento...</div>", unsafe_allow_html=True)
                    st.markdown(f"**⚪ {linha.get('Data Apresentação', 'Data não informada')}**\n└ *Proposição apresentada na Câmara dos Deputados.*")

            evento = st.dataframe(
                df_exibicao,
                column_config={
                    "ID": None,
                    "Link": st.column_config.LinkColumn(), 
                    "Documento PDF": st.column_config.LinkColumn()
                },
                width='stretch', hide_index=True, on_select="rerun", selection_mode="single-row"
            )

            if evento and evento["selection"]["rows"]:
                idx = evento["selection"]["rows"][0]
                mostrar_modal_tramitacao_aba2(df_exibicao.iloc[idx])

    # --- ABA 3: BUSCA GLOBAL ---
    with tab_busca_global:
        st.subheader("🌐 Busca na Base Completa da Câmara")
        busca_livre = st.text_input("🔍 Digite o número da norma (Ex: PL 2338/2023):")
        
        if busca_livre:
            with st.spinner("Buscando..."):
                df_completo = load_base_completa()
                if not df_completo.empty:
                    termo = busca_livre.lower()
                    mask = (df_completo['Norma'].str.lower().str.contains(termo, na=False) |
                            df_completo['Ementa'].str.lower().str.contains(termo, na=False) |
                            df_completo['Autor'].str.lower().str.contains(termo, na=False))
                    df_resultado = df_completo[mask].copy()
                    
                    if not df_resultado.empty:
                        if 'norma' in df_csv_completo.columns and 'score_relevancia' in df_csv_completo.columns:
                            df_notas = df_csv_completo[['norma', 'score_relevancia']].copy()
                            df_resultado['norma_clean'] = df_resultado['Norma'].str.replace(" ", "").str.lower()
                            df_notas['norma_clean'] = df_notas['norma'].str.replace(" ", "").str.lower()
                            df_resultado = df_resultado.merge(df_notas[['norma_clean', 'score_relevancia']], on='norma_clean', how='left')
                            df_resultado['Score'] = df_resultado['score_relevancia'].apply(lambda x: f"{float(x):.4f}" if pd.notnull(x) else "Abaixo do corte")
                            df_resultado = df_resultado.drop(columns=['norma_clean', 'score_relevancia'])
                        else:
                            df_resultado['Score'] = "Sem score"

                        cols = ['Norma', 'Score', 'Data de Apresentação', 'Autor', 'Situação', 'Ementa', 'Link']
                        df_resultado = df_resultado[[c for c in cols if c in df_resultado.columns]]

                    st.success(f"Encontrados: {len(df_resultado)}")
                    st.dataframe(df_resultado, column_config={"Link": st.column_config.LinkColumn()}, width='stretch', hide_index=True)
                else:
                    st.error("Nenhum dado bruto encontrado.")