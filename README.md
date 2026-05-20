# Projeto-Dashboard: IA OASIS
O Dashboard: IA OASIS é uma plataforma avançada de dashboard e pesquisa de projetos de lei. Diferente dos algoritmos de busca convencionais, a ferramenta utiliza Modelos de Linguagem de Grande Escala (LLMs) para realizar uma análise contextual das ementas dos projetos. Nosso objetivo é integrar projetos de lei da Câmara dos Deputados e do Senado para oferecer uma visão geral ao pesquisador, por meio de gráficos detalhados, rankings e listas personalizadas. 

### O que é uma LLM?
Um Modelo de Linguagem de Grande Escala (LLM) é um tipo de programa de inteligência artificial (IA) pré-treinada com uma grande quantidade de dados, que pode reconhecer e gerar texto, analisar dados, entre outras tarefas. O Modelo escolhido para o nosso programa é o "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", uma ia treinada e focada em análise de texto.

É Importante ressaltar que se trata de um modelo pré-treinado, em nosso projeto não desenvolvemos uma inteligência artificial do zero, isso significa que não estamos rastreando e nem coletando nenhum dado de nenhum usuário.

## Como funciona o Dashboard
Atualmente o Dashboard: IA OASIS está disponível de forma online 100% gratuita. o projeto ainda está em fase de prototipagem e por enquanto pode ser acessador por: https://dashboard-oasis.streamlit.app/

Hoje possuimos duas abas principais, "Pesquisa" e "Atualizar Base de Dasos (BETA)":

- Pesquisa: Possui as principais funções do aplicativo, focada nos resultados da pesquisa, é nossa tela princial.
- Atualizar Base de Dados (BETA): Essa aba possui apenas um botão para atualizar o banco de dados com os projetos de lei mais recente. Por se tratar de um protótipo e de limitações da nossa hospedagem gratuita, esse processo é bem demorado, por isso está em outra aba e com um aviso antes. 

Para utilizar o Dashboard, basta preencher as barras de busca de acordo com seu interesse de pesquisa. Hoje o programa tem duas barras de pesquisa, a principal (obrigatória) e a secundária (opcional).

```
Exemplos de pesquisa:
Tema Principal: Inteligência Artificial -> Tema Secundário: Ensino Superior 
Tema Principal: Inteligência Artificial 
Tema Principal: Imposto -> Tema Secundário: Eletrônicos 
```


Na aba principal temos 3 Abas: "Visão Geral", "Lista Filtrada", "Busca Global(Base Completa)"

- Visão Geral: Nessa aba são informadas as principais estatísticas sobre a pesquisa. Dados importantes como a quantidade de projetos filtrados, partidos envolvidos e etc. É nessa aba que se concentram todos os diversos gráficos do Dashboard. Todos os gráficos e pesquisa são gerados a partir de uma filtragem dos temas de interesse.

- Lista Filtrada: Nessa aba são organizadas todos os projetos de lei, organizado por relevância de acordo com seu tema. São exibidas todas as principais informações, com liberdade total para várias ferramentas, como trocar as colunas arrastando com o mouse, pesquisar na lista, tela cheia, baixar como CSV, entre outros. Todas as preposições filtradas podem ser acessadas pelos links na sessão "Preposições" pra o acesso completo das informações dos projetos de lei. A Barra lateral Possuem diversas funções de filtragem, e todas elas estão relacionadas com essa aba, como por exemplo, a seleção entre organizar por relevância do tema ou por data, mais recente ou mais antiga.

- Busca Global (Base Completa): Essa aba é uma aba complementar, caso queira buscar da base completa, não apenas dos projetos filtrados, útil para pesquisar algum projeto específico, deputado, ementa, situação, o que for necessário para complementar sua pesquisa.

Esperamos que esse Dashboard seja útil para suas pesquisas!
# Guias de Instalação:
AVISO: A Instalação do programa NÃO está sendo o foco de desenvolvimento no momento, recomenda-se instalar apenas se tiver um conhecimento significativo de programação. 
## Instalação Windows
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

- Instalação Windows:
    - Baixe esse diretório no seu computador, ou clone ele utilizando o Git

    - Baixe as bibliotecas necessárias pelo terminal, utilizando o comando ("pip install -r requirements.txt")
        - (se não funcionar, basta instalar cada uma das bibliotecas listadas no arquivo requirements.txt)

    - É importante instalar completamente o MySQL, e verificar se o localhost root está configurado


## Instalação Linux

1) Clone o projeto para para o seu computador
```
git clone <url-do-repositorio>
cd <nome-do-projeto>
```

2) Dentro da pasta principal, crie um ambiente virtual para o projeto:
```
python -m venv venv
```
ou (dependendo da versão do python instalada)

```
python3 -m venv venv
```

3) Ativar o ambiente virtual criado:


```
source venv/bin/activate
```
4) Atualizar pip (recomendado):
```
pip install --upgrade pip
```

5) Instalar as dependências
```
pip install -r requirements.txt
```


## Como Configurar A Instalação do Dashboard
### configurando pela primeira vez
```
Para executar o Dashboard, apenas execute o arquivo main.py (dois cliques ou execute-o por algum interpretador)

O código cria um arquivo cache local com todas as proposições em um determinado período de tempo ([default: 2015 - hoje em dia], alterável na linha 21 do código config.py), hoje incluimos o banco de dados no github, porém na primeira execução ocorrerá uma atualização dos dados. O processo da atualizaçãp dessa cache é bastante demorado, porém apenas ocorre na primeira execução, por isso não se assuste. nas próximas execuções, as filtragens ocorrem de forma rápida.

Para Alterar os parâmetros de configuração, recomenda-se criar uma pasta ".streamlit" com um arquivo "secrets.toml", utilize esses parâmetros e o configure de acordo:
    
    HOST = "localhost"
    PORTA = 0
    USUARIO = "root"
    SENHA = "INSIRA_SUA_SENHA"
    NOME = "Oasis"
    HF_TOKEN = " " #Utilize um Token caso tenha conta no Hugging Face
    CERTIFICADO = """ """
    
Eses arquivos não são disponabilizados no github por questões de segurança.

Não altere os nomes das variáveis, remomendado alterar o valor apenas da sua senha do localhost configurado no MySQL na variável "SENHA"

Agora seu Dashboard está configurado.
```
## Como rodar o código automaticamente
streamlit run main.py

# Especificações:
## Arquivos
- **_config.py_**: Arquivo de configuração, que contém as variáveis mais importantes no mesmo locar, para melhor controle e experiência do usuário;
- **_acess_api.py_**, **_coletor_camara2.py_**, **_filtrador_hibrido_v3_final.py_**, **_gerador_keywords.py_** : São arquivos q fazem acesso a API (atualmente somente da Câmara) e retorna PL's, PLP's e PEC's, vetorizados, que tenham similiaridade semântica determinada com uma frase escolhida (como "Projetos de lei sobre IA's"), em formato json, e salva em arquivos CSV para serem analisados;
- **_embeddings.py_**: Arquivo utilizado para atualizar os embedings da base de dados;
- **_create_database.sql_**: Cria um banco de dados em MySQL para armazenar os projetos de lei;
- **_insert_data.py_**: Lê as linhas do CSV e salva como instâncias do banco criado, populando-o;
- **_dashboard.py_**: cria o dashboard usando as informações armazenadas no banco de dados MySQL;
- **_main.py_**: arquivo main, organiza a execução em sequencia de todos os arquivos necessários para o funcionamento do dashboard;
- **_requirements.txt_**: Arquivo que contém todas as bibliotecas necessárias para executar os códigos python;
- Outros arquivos serão gerados durante a execução da aplicação;
## Pastas
-**_banco_de_dados_local_**: Pasta de organização para guardar diversos dados úteis para a pesquisa, de forma modularizada e organizada
- **_projetos_em_csv_**: Pasta para armazenar os CSVs gerados pelo acesso_api.py
(caso a pasta "projetos_em_csv" não exista, a main.py criará ela automaticamente)  

