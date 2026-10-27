"""
Nichos = personas (personas.py) + links de exemplo do formato (exemplos.json).

O programa NÃO usa mais hashtags escritas à mão: ele abre os vídeos de
exemplo de cada nicho, aprende o formato deles (formato.py) e caça vídeos
parecidos. Para mudar um nicho, troque os links em exemplos.json ou pela
própria página.
"""

import json
import os
import re

from personas import listar_personas

ARQ_EXEMPLOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exemplos.json")


def limpar_link(url):
    """Tira barras de markdown e parâmetros (?is_from_webapp=...) do link."""
    url = url.strip().replace("\\", "")
    m = re.search(r"https?://(www\.|m\.|vm\.|vt\.)?tiktok\.com/\S+", url)
    if not m:
        return None
    return m.group(0).split("?")[0].rstrip("/")


def carregar_exemplos():
    try:
        with open(ARQ_EXEMPLOS, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def salvar_exemplos(nome, links):
    dados = carregar_exemplos()
    dados[nome] = [l for l in (limpar_link(x) for x in links) if l]
    with open(ARQ_EXEMPLOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return dados[nome]


def listar_nichos():
    """Devolve [{nome, genero, exemplos}] para cada persona cadastrada."""
    exemplos = carregar_exemplos()
    return [
        {"nome": p["nome"], "genero": p["genero"], "exemplos": exemplos.get(p["nome"], [])}
        for p in listar_personas()
    ]


def obter_nicho(nome):
    for n in listar_nichos():
        if n["nome"] == nome:
            return n
    return None
