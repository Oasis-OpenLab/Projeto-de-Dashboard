import streamlit as st
import pesquisa
import dashboard

st.set_page_config(page_title="Dashboard OASIS", layout="wide")
st.title("🏛️ Dashboard dos Projetos de Lei - IA OASIS")

termo_pesquisa = st.text_input(label="Pesquisar Projeto de Lei")

# 1. Cria a trava de memória (começa como Falsa)
if 'ia_concluida' not in st.session_state:
    st.session_state.ia_concluida = False

# 2. A GAIOLA DA IA: Tudo que é pesado fica preso neste botão
if st.button('Pesquisar'):
    with st.spinner('A IA OASIS está processando os dados. Aguarde...'):
        
        with open( 'banco_de_dados_local/pesquisa.txt', 'w', encoding='utf-8') as arquivo:
            if termo_pesquisa != (None or " ") and termo_pesquisa != arquivo.read:
                 arquivo.write(termo_pesquisa)
                 arquivo.close()
                 st.cache_data.clear()
            else:
                arquivo.write(termo_pesquisa)
                arquivo.close()

        # Roda o processamento
        pesquisa.pesquisar()
        
        # Destrava a memória avisando que a IA já terminou
        st.session_state.ia_concluida = True

# 3. A VITRINE: Só desenha se a IA já concluiu o trabalho
if st.session_state.ia_concluida:
    st.success("Busca finalizada! Os dados já estão disponíveis no painel.")
    st.markdown("---")
    
    # Chama a função que desenha a tela (que você criou no dashboard.py)
    dashboard.rodar_dashboard()