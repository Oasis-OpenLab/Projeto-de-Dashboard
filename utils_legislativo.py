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
    if not texto: return ""
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def limpar_padroes_regex(texto):
    texto = re.sub(r'\bde\s+\d{4}\b', ' ', texto) 
    texto = re.sub(r'lei\s+n[ºo°]?\s*[\d\.]+', ' ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bart[\.\s]\s*\d+[ºo°]?', ' ', texto, flags=re.IGNORECASE) 
    texto = re.sub(r'§\s*\d+[ºo°]?', ' ', texto)
    texto = re.sub(r'\binciso\s+[ivxlcdm]+\b', ' ', texto, flags=re.IGNORECASE)
    return texto

def limpar_ementa_para_vetorizacao(texto):
    if not texto: return ""
    texto = limpar_texto_basico(texto)
    texto = limpar_padroes_regex(texto)
    for termo in STOPWORDS_LEGISLATIVAS:
        texto = texto.replace(termo, " ")
    return " ".join(texto.split())

def validar_tag(tag):
    if not tag: return None
    t_limpo = limpar_texto_basico(tag).strip()
    if len(t_limpo) <= 3 or t_limpo in BLACKLIST_KEYWORDS:
        return None
    return t_limpo.upper()

def obter_legislatura(ano):
    """NOVO: Retorna a qual legislatura o ano pertence para fazer o Sharding"""
    try:
        ano = int(ano)
        if ano >= 2023: return "leg57"
        elif ano >= 2019: return "leg56"
        elif ano >= 2015: return "leg55"
        elif ano >= 2011: return "leg54"
        else: return "leg_antiga"
    except:
        return "leg_desconhecida"