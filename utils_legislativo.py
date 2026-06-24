"""
Módulo de utilitários para Processamento de Linguagem Natural (NLP) legislativo.

Fornece funções para padronização, limpeza e tratamento de textos jurídicos 
brutos extraídos da API da Câmara. O objetivo é remover ruídos (como numerações 
de leis e jargões burocráticos) para otimizar a criação de vetores de alta 
qualidade pelos modelos de Inteligência Artificial.
"""

import re
import unicodedata

# --- STOPWORDS E BLACKLIST ---
STOPWORDS_LEGISLATIVAS = [
    "dispõe sobre", "dispoe sobre", "trata de", "institui o", "institui a",
    "cria o", "cria a", "estabelece", "normas gerais", "providências",
    "dá outras providências", "da outras providencias", "para os fins",
    "nos termos", "com a finalidade de", "visando a", "a fim de",
    "para dispor sobre", "para prever", "para estender", "para aperfeiçoar",
    "altera a lei", "altera o decreto", "altera os", "altera as",
    "acrescenta", "insere", "modifica", "revoga", "redação dada",
    "redacao dada", "nova redação", "suprime", "veda a", "veda o",
    "projeto de lei", "pl", "medida provisória", "mpv", "pec",
    "código penal", "código civil", "estatuto", "constituição federal",
    "decreto-lei", "decreto lei", "lei brasileira", "lei de",
    "caput", "parágrafo único", "paragrafo unico", "artigo", "inciso"
]

BLACKLIST_KEYWORDS = {
    "projeto", "lei", "sobre", "alteracao", "criacao", "instituicao", 
    "federal", "nacional", "publica", "publico", "regulamentacao", 
    "normatizacao", "dispositivos", "providencias", "vigencia", 
    "anexo", "provisoria", "urgencia", "uniao", "municipios", "estados", 
    "distrito", "territorio", "administracao", "direta", "indireta", 
    "ambito", "autorizacao", "obrigatoriedade", "fixacao", "prorrogacao",
    "acrescenta", "revoga", "substitui", "autoriza", "obriga"
}

def limpar_texto_basico(texto):
    """
    Remove acentuação, caracteres especiais invisíveis e converte o texto para minúsculas.

    Args:
        texto (str): O texto bruto que precisa ser normalizado.

    Returns:
        str: Texto em minúsculas e sem acentos, ou string vazia se nulo.
    """
    if not texto: return ""
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def limpar_padroes_regex(texto):
    """
    Remove menções repetitivas a artigos, incisos, parágrafos e datas específicas.
    
    Utiliza expressões regulares para limpar jargões estruturais que não agregam
    valor semântico ao tema do projeto.

    Args:
        texto (str): O texto a ser processado com as regex.

    Returns:
        str: O texto com os padrões legais removidos.
    """
    texto = re.sub(r'\bde\s+\d{4}\b', ' ', texto) 
    texto = re.sub(r'lei\s+n[ºo°]?\s*[\d\.]+', ' ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bart[\.\s]\s*\d+[ºo°]?', ' ', texto, flags=re.IGNORECASE) 
    texto = re.sub(r'§\s*\d+[ºo°]?', ' ', texto)
    texto = re.sub(r'\binciso\s+[ivxlcdm]+\b', ' ', texto, flags=re.IGNORECASE)
    return texto

def limpar_ementa_para_vetorizacao(texto):
    """
    Função orquestradora que prepara a ementa de um projeto para a Inteligência Artificial.

    Aplica a limpeza básica, remove padrões de formatação legal (regex) e 
    filtra as stopwords específicas do contexto legislativo.

    Args:
        texto (str): Ementa original do projeto de lei.

    Returns:
        str: Ementa limpa e condensada, contendo apenas palavras com peso semântico.
    """
    if not texto: return ""
    texto = limpar_texto_basico(texto)
    texto = limpar_padroes_regex(texto)
    for termo in STOPWORDS_LEGISLATIVAS:
        texto = texto.replace(termo, " ")
    return " ".join(texto.split())

def validar_tag(tag):
    """
    Valida e padroniza as palavras-chave (indexação) vinculadas aos projetos.

    Rejeita tags muito curtas (<= 3 letras) ou que constem na lista de bloqueio
    (blacklist) por serem genéricas demais.

    Args:
        tag (str): Palavra-chave ou termo de indexação bruto.

    Returns:
        str ou None: A tag em formato maiúsculo se válida, ou None se rejeitada.
    """
    if not tag: return None
    t_limpo = limpar_texto_basico(tag).strip()
    if len(t_limpo) <= 3 or t_limpo in BLACKLIST_KEYWORDS:
        return None
    return t_limpo.upper()

def obter_legislatura(ano):
    """
    Classifica um ano na sua respectiva legislatura da Câmara dos Deputados.

    Função utilizada para rotear e particionar dados em blocos (sharding), 
    evitando que o sistema processe arquivos monolíticos e pesados.

    Args:
        ano (int ou str): O ano de apresentação do projeto.

    Returns:
        str: A string representativa da legislatura (ex: 'leg57', 'leg56').
    """
    try:
        ano = int(ano)
        if ano >= 2023: return "leg57"
        elif ano >= 2019: return "leg56"
        elif ano >= 2015: return "leg55"
        elif ano >= 2011: return "leg54"
        else: return "leg_antiga"
    except:
        return "leg_desconhecida"