# Projeto-de-Dashboard
O projeto tem como objetivo importar das API's da Câmara dos Deputados e do Senado os projetos de lei que falem sobre inteligências artificiais e tecnologias algorítmicas, e seus respectivos impactos na educação e na sociedade como um todo.

## Arquivos
- **_acess_api.py_**: Faz acesso a API (atualmente somente da Câmara) e retorna PL's, PLP's e PEC's, que tenham similiaridade semântica determinada com uma frase escolhida (como "Projetos de lei sobre IA's"), em formato json, e salva em arquivos CSV para serem analisados;
- **_create_database.sql_**: Cria um banco de dados em SQL para armazenar os projetos de lei;
- **_insert_data.py_**: Lê as linhas do CSV e salva como instâncias do banco criado, populando-o;

## Pastas
- **_projetos_em_csv_**: Pasta para armazenar os CSVs gerados pelo acesso_api.py