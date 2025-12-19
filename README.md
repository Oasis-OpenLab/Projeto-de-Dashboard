# Projeto-de-Dashboard
O projeto é uma ferramenta de pesquisa de projetos de lei. Nosso principal objetivo é importar da Câmara dos Deputados e do Senado os projetos de lei que falem sobre inteligências artificiais e tecnologias algorítmicas, e seus respectivos impactos na educação e na sociedade como um todo, através de gráficos, rankings e listas. O tema de pesquisa pode ser alterado.

## Como Usar o Dashboard pela Primeira Vez
Para utilizar o Dashboard, existem alguns passos a serem concluidos:

- Utilizaremos alguns programas, listados abaixo. Para a instalação do Python, é importante lembrar de criar as paths em seu computador, para isso, apenas marque a caixa "criar path" durante o processo de instalação.
- Programas essenciais:
    - Python (versão recomendada: 3.11 ou 3.12)
        - download: https://www.python.org/downloads/ 
    - MySQL (versão recomendada: Windows)
        - download: https://dev.mysql.com/downloads/
- Programas recomendados:
    - Git
        - download: https://git-scm.com/install/windows
    - interpretador python/mysql (ex: VsCode)

- Antes da primeira execução:
    - Baixe esse diretório no seu computador, ou clone ele utilizando o Git

    - Baixe as bibliotecas necessárias pelo terminal, utilizando o comando ("pip install -r requirements.txt")
        - (se não funcionar, basta instalar cada uma das bibliotecas listadas no arquivo requirements.txt)

    - É importante instalar completamente o MySQL, e verificar se o localhost root está configurado

    - verificar se a senha nos arquivos é a mesma que no seu usuário root MySQL
        - na main.py, altere o valor da variável "DB_PASWORD" pela sua senha (linha 14 do código)
        - na insert_data.py, altere o valor da variável "password" pela sua senha (linha 5 do código)
        - na dashboard.py, altere o valor da variável "password" pela sua senha (linha 28 do código)

- Primeira execução:
    - Abra o arquivo main.py (dois cliques ou execute-o por algum interpretador)

## Como funciona o Dashboard
Para executar o Dashboard, apenas execute o arquivo main.py (dois cliques ou execute-o por algum interpretador)

O código cria um arquivo cache local com todas as proposições em um determinado período de tempo ([default: 2023 - hoje em dia], alterável na linha 22 do código acess_api.py), o processo da criação dessa cache é demorado, porém apenas ocorre na primeira execução, por isso não se assuste. nas próximas execuções, as filtragens ocorrem de forma rápida.

Todos os gráficos e pesquisa são gerados a partir de uma filtragem de um tema de interesse, do conteúdo da cache. Esse tema pode ser alterado para cada pesquisa (default: "Regulamentação inteligência artificial e algoritmos").

O tema de interesse pode ser alterado no arquivo "acess_api.py", na variável "CONSULTA_USUARIO", na linha 27 do código.

Após executar a main.py, o Dashboard será aberto com todas a funcionalidades a sua disposição. os gráficos são divididos em 4 sessões (Visão Geral, Partidos, Autores e Temas), com a lista das preposições na sessão "Preposições". A esquerda, ficam os filtros relacionados a sessão "Preposições", e abaixo nos "Gráficos", ficam todos os gráficos visíveis, que podem ser desmarcados. Todos os gráficos podem ser visto em tela cheia.

Todas as preposições filtradas podem ser acessadas pelos links na sessão "Preposições".

Esperamos que esse Dashboard seja útil para suas pesquisas!

## Como rodar por código automaticamente
python main.py

## Como rodar por código manualmente
python acess_api.py

~ cria o banco no computador usando create_database.sql ~

python insert_data.py

streamlit run dashboard.py
# Especificações:
## Arquivos
- **_acess_api.py_**: Faz acesso a API (atualmente somente da Câmara) e retorna PL's, PLP's e PEC's, que tenham similiaridade semântica determinada com uma frase escolhida (como "Projetos de lei sobre IA's"), em formato json, e salva em arquivos CSV para serem analisados;
- **_create_database.sql_**: Cria um banco de dados em MySQL para armazenar os projetos de lei;
- **_insert_data.py_**: Lê as linhas do CSV e salva como instâncias do banco criado, populando-o;
- **_dashboard.py_**: cria o dashboard usando as informações armazenadas no banco de dados MySQL;
- **_main.py_**: arquivo main, organiza a execução em sequencia de todos os arquivos necessários para o funcionamento do dashboard;
- **_requirements.txt_**: Arquivo que contém todas as bibliotecas necessárias para executar os códigos python;
- Outros arquivos serão gerados durante a execução da aplicação;
## Pastas
- **_projetos_em_csv_**: Pasta para armazenar os CSVs gerados pelo acesso_api.py
(caso a pasta "projetos_em_csv" não exista, a main.py criará ela automaticamente)  

