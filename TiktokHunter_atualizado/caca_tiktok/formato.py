"""
Aprende o FORMATO de um nicho a partir dos vídeos de exemplo e dá uma
nota de 0 a 1 para o quanto um vídeo qualquer se parece com ele.

O que entra no "perfil do formato":
  - hashtags e palavras da legenda dos exemplos
  - o som/música usado (vídeos do mesmo formato costumam usar o mesmo áudio)
  - os criadores que postam esse formato
  - a faixa de duração
  - a aparência (miniatura) — ver visual.py
"""

import hashlib
import json
import math
import os
import re
from collections import Counter

import coletor
import visual

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_CACHE = os.path.join(PASTA, "cache_formatos.json")

# Peso de cada sinal na nota final (só entram os sinais disponíveis)
PESOS = {
    "som": 0.30,
    "hashtags": 0.25,
    "palavras": 0.15,
    "visual": 0.25,
    "duracao": 0.05,
}

# Hashtags/palavras genéricas demais para dizer algo sobre o formato
GENERICAS = set("""
fyp fy foryou foryoupage fypシ fypage viral viralvideo viraltiktok parati paravoce
paravocê pravoce foryourpage tiktok tiktokbrasil trend trending explore xyzbca
capcut brasil br de da do das dos a o e é em um uma para pra com no na nos nas
que se por os as the and to of in you your this my me is it on for with esse essa
isso ela ele eu voce você mais muito tem ter vai foi sem bem link bio
""".split())

YDL = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}


# ---------- leitura de vídeos ----------

def info_video(url):
    return coletor.info_video(url)


def autor_do_link(url):
    m = re.search(r"tiktok\.com/@([^/?]+)", url or "")
    return m.group(1).lower() if m else ""


def legenda(info):
    return (info.get("description") or info.get("title") or "").strip()


def extrair_hashtags(texto):
    return [h for h in re.findall(r"#([\wÀ-ÿ]+)", texto.lower()) if h not in GENERICAS]


def extrair_palavras(texto):
    sem_tags = re.sub(r"#[\wÀ-ÿ]+|@[\w.]+|https?://\S+", " ", texto.lower())
    return [p for p in re.findall(r"[a-zà-ÿ]{3,}", sem_tags) if p not in GENERICAS]


def nome_som(info):
    """Identifica o áudio do vídeo (música ou 'som original - fulano')."""
    faixa = info.get("track") or ""
    artista = info.get("artist") or ", ".join(info.get("artists") or [])
    som = f"{faixa} - {artista}".strip(" -").lower()
    return som or None


# ---------- aprender o formato ----------

def _chave(links):
    # O modo visual entra na chave: trocar de modo faz reaprender o formato
    return hashlib.md5(("|".join(sorted(links)) + visual.MODO).encode()).hexdigest()


def _ler_cache():
    try:
        with open(ARQ_CACHE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def aprender_formato(links, log=print, usar_cache=True):
    """Abre os exemplos e devolve o perfil do formato (dict serializável)."""
    cache = _ler_cache()
    chave = _chave(links)
    if usar_cache and chave in cache:
        log("📚 Formato já aprendido (cache).")
        return cache[chave]

    tags, palavras, sons, autores, duracoes, thumbs, ids = Counter(), Counter(), Counter(), [], [], [], []
    musicas = {}
    for url in links:
        log(f"🎓 Estudando exemplo: {url}")
        try:
            info = info_video(url)
        except Exception as erro:
            log(f"   ⚠️ não consegui abrir: {erro}")
            continue
        if not info:
            log("   ⚠️ não consegui abrir este exemplo (o TikTok pode ter bloqueado).")
            continue
        texto = legenda(info)
        tags.update(extrair_hashtags(texto))
        palavras.update(extrair_palavras(texto))
        if nome_som(info):
            sons[nome_som(info)] += 1
        if info.get("music_id"):
            musicas[info["music_id"]] = nome_som(info) or ""
        autores.append((info.get("uploader") or autor_do_link(url)).lower())
        if info.get("duration"):
            duracoes.append(float(info["duration"]))
        if info.get("thumbnail"):
            thumbs.append(info["thumbnail"])
        ids.append(str(info.get("id")))
        log(f"   legenda: {texto[:90]!r}")
        log(f"   som: {nome_som(info)}  |  {info.get('duration')}s")

    if not ids:
        raise RuntimeError("Nenhum exemplo pôde ser aberto. Confira os links ou atualize o yt-dlp.")

    perfil = {
        "links": links,
        "ids": ids,
        "hashtags": dict(tags.most_common(25)),
        "palavras": dict(palavras.most_common(25)),
        "sons": dict(sons),
        "musicas": musicas,
        "autores": sorted(set(a for a in autores if a)),
        "duracao": [min(duracoes), max(duracoes)] if duracoes else None,
        "assinaturas_visuais": [s for s in (visual.assinatura_url(t) for t in thumbs) if s],
    }
    cache[chave] = perfil
    with open(ARQ_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    return perfil


# ---------- comparar um vídeo com o formato ----------

def _cosseno(contagem_a, lista_b):
    if not contagem_a or not lista_b:
        return 0.0
    b = Counter(lista_b)
    comum = sum(contagem_a[k] * b[k] for k in b if k in contagem_a)
    na = math.sqrt(sum(v * v for v in contagem_a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return comum / (na * nb) if na and nb else 0.0


def pontuar(video, perfil, assinatura=None):
    """
    Devolve (nota 0-1, motivos). `video` precisa de: legenda, som, duracao.
    `assinatura` é a assinatura visual da miniatura do vídeo (opcional).
    """
    notas, motivos = {}, []
    texto = video.get("legenda") or ""

    if perfil["hashtags"]:
        tags_v = extrair_hashtags(texto)
        notas["hashtags"] = _cosseno(perfil["hashtags"], tags_v)
        iguais = [t for t in tags_v if t in perfil["hashtags"]]
        if iguais:
            motivos.append("#" + " #".join(iguais[:4]))

    if perfil["palavras"]:
        notas["palavras"] = _cosseno(perfil["palavras"], extrair_palavras(texto))

    if perfil["sons"] or perfil.get("musicas"):
        som = video.get("som")
        mesmo_id = video.get("music_id") and video["music_id"] in perfil.get("musicas", {})
        notas["som"] = 1.0 if mesmo_id or (som and som in perfil["sons"]) else 0.0
        if notas["som"]:
            motivos.append("mesmo som")

    if perfil["duracao"] and video.get("duracao"):
        lo, hi = perfil["duracao"]
        d = video["duracao"]
        distancia = 0 if lo - 3 <= d <= hi + 3 else min(abs(d - lo), abs(d - hi))
        notas["duracao"] = max(0.0, 1 - distancia / 10)

    if perfil["assinaturas_visuais"] and assinatura:
        sim = max(visual.similaridade(assinatura, s) for s in perfil["assinaturas_visuais"])
        notas["visual"] = sim
        if sim >= 0.8:
            motivos.append("visual parecido")

    if not notas:
        return 0.0, motivos
    peso_total = sum(PESOS[k] for k in notas)
    nota = sum(PESOS[k] * v for k, v in notas.items()) / peso_total
    return round(nota, 3), motivos


def resumo(perfil):
    """Versão curta do perfil para mostrar na página."""
    return {
        "hashtags": list(perfil["hashtags"])[:10],
        "palavras": list(perfil["palavras"])[:10],
        "sons": list(perfil["sons"]),
        "autores": perfil["autores"],
        "duracao": perfil["duracao"],
        "visual": bool(perfil["assinaturas_visuais"]),
        "modo_visual": visual.MODO,
        "exemplos_lidos": len(perfil["ids"]),
    }
