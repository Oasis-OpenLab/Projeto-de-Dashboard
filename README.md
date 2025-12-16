# Projeto-de-Dashboard
O projeto tem como objetivo importar das API's da Câmara dos Deputados e do Senado os projetos de lei que falem sobre inteligências artificiais e tecnologias algorítmicas, e seus respectivos impactos na educação e na sociedade como um todo.

## Arquivos
- **_acess_api.py_**: Faz acesso a API (atualmente somente da Câmara) e retorna PL's, PLP's e PEC's, que tenham similiaridade semântica determinada com uma frase escolhida (como "Projetos de lei sobre IA's"), em formato json, e salva em arquivos CSV para serem analisados;
- **_create_database.sql_**: Cria um banco de dados em SQL para armazenar os projetos de lei;
- **_insert_data.py_**: Lê as linhas do CSV e salva como instâncias do banco criado, populando-o;
- **_dashboard.py_**: cria o dashboard usando as informações armazenadas no bando dde dados SQL;
- **_main.py_**: arquivo main, organiza a execução em sequencia de todos os arquivos necessários para o funcionamento do dashboard;
- **_requirements.txt_**: Arquivo que contém todas as bibliotecas necessárias para rodar o código;

## Pastas
- **_projetos_em_csv_**: Pasta para armazenar os CSVs gerados pelo acesso_api.py
(caso a pasta "projetos_em_csv" não exista, a main.py criará ela automaticamente)  

## Primeira vez rodando o código:
Alterar a senha do sql nos arquivos
instalar todas as biliotecas necessarias: ("pip install -r requirements.txt")

## Como rodar o código automaticamente
python main.py

## Como rodar o código manualmente
python acess_api.py

~ cria o banco no computador usando create_database.sql ~

python insert_data.py

streamlit run dashboard.py
