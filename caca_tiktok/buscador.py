"""
Caçador de vídeos no TikTok POR FORMATO.

Como funciona:
  1. Abre os links de exemplo do nicho (exemplos.json) e aprende o formato
     (som, legenda, hashtags, criadores, duração e aparência) -> formato.py
  2. Junta candidatos de onde esse formato aparece:
       - outros vídeos dos criadores dos exemplos
       - as hashtags que os PRÓPRIOS exemplos usam (descobertas sozinhas)
  3. Dá uma nota de compatibilidade para cada candidato de até DURACAO_MAX
     segundos e devolve no máximo 4 links, organizados como pedido.

Uso no terminal:
    python buscador.py "Ruiva com Sardas" 4
"""

import sys

import yt_dlp

import formato
import visual
from nichos import obter_nicho

DURACAO_MAX = 18        # segundos
MAX_LINKS = 4           # limite de links por pedido
VIDEOS_POR_FONTE = 40   # quantos vídeos olhar em cada criador/hashtag
TOP_HASHTAGS = 6        # quantas hashtags aprendidas usar como fonte
MAX_DETALHES = 80       # limite de vídeos abertos um a um (deixa a busca mais rápida)
NOTA_MINIMA = 0.20      # abaixo disso o vídeo não é considerado do mesmo formato
BUSCAR_NOS_CRIADORES = True

# Contas que nunca entram nos resultados (ex.: o seu próprio perfil)
AUTORES_IGNORADOS = {"infinity_achados"}

ORDENS = {
    "formato": ("Mais parecidos com o formato", lambda v: -v["nota"]),
    "views": ("Mais vistos", lambda v: -(v["views"] or 0)),
    "curtidas": ("Mais curtidos", lambda v: -(v["curtidas"] or 0)),
    "recentes": ("Mais recentes", lambda v: -(v["data"] or 0)),
    "curtos": ("Mais curtos", lambda v: v["duracao"]),
}


def _listar(url, limite):
    """Lista vídeos de uma página (perfil ou hashtag) sem abrir cada um."""
    opts = dict(formato.YDL, extract_flat="in_playlist", playlistend=limite)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return [e for e in (info or {}).get("entries") or [] if e]


def _normalizar(e, fonte):
    url = e.get("webpage_url") or e.get("url") or ""
    autor = (e.get("uploader") or e.get("channel") or formato.autor_do_link(url) or "").lower()
    if not url.startswith("http"):
        url = f"https://www.tiktok.com/@{autor or '_'}/video/{e.get('id')}"
    return {
        "url": url.split("?")[0],
        "id": str(e.get("id")),
        "autor": autor,
        "legenda": formato.legenda(e),
        "som": formato.nome_som(e),
        "duracao": e.get("duration"),
        "views": e.get("view_count"),
        "curtidas": e.get("like_count"),
        "data": e.get("timestamp"),
        "thumb": e.get("thumbnail"),
        "fonte": fonte,
    }


def _fontes(perfil):
    if BUSCAR_NOS_CRIADORES:
        for autor in perfil["autores"]:
            if autor not in AUTORES_IGNORADOS:
                yield f"@{autor}", f"https://www.tiktok.com/@{autor}"
    for tag in list(perfil["hashtags"])[:TOP_HASHTAGS]:
        yield f"#{tag}", f"https://www.tiktok.com/tag/{tag}"


def cacar_videos(nome_nicho, quantidade=MAX_LINKS, ordem="formato", log=print):
    nicho = obter_nicho(nome_nicho)
    if not nicho:
        raise ValueError(f"Nicho '{nome_nicho}' não existe.")
    if not nicho["exemplos"]:
        raise ValueError(f"Cadastre pelo menos 1 link de exemplo para '{nome_nicho}'.")
    quantidade = max(1, min(int(quantidade), MAX_LINKS))
    ordem = ordem if ordem in ORDENS else "formato"

    perfil = formato.aprender_formato(nicho["exemplos"], log=log)
    log(f"🧠 Formato: sons={list(perfil['sons'])[:2]} | "
        f"hashtags={list(perfil['hashtags'])[:6]} | criadores={perfil['autores']}")

    vistos = set(perfil["ids"])
    aprovados, detalhes = [], 0
    alvo = quantidade * 3  # folga para escolher os melhores

    for rotulo, url in _fontes(perfil):
        if len(aprovados) >= alvo:
            break
        log(f"🔎 {rotulo} ...")
        try:
            entradas = _listar(url, VIDEOS_POR_FONTE)
        except Exception as erro:
            log(f"   ⚠️ falhou: {erro}")
            continue
        log(f"   {len(entradas)} vídeos listados")

        for e in entradas:
            v = _normalizar(e, rotulo)
            if v["id"] in vistos or v["autor"] in AUTORES_IGNORADOS:
                continue
            vistos.add(v["id"])

            # A listagem rápida às vezes não traz legenda/duração: abre o vídeo
            if (v["duracao"] is None or not v["legenda"]) and detalhes < MAX_DETALHES:
                detalhes += 1
                try:
                    completo = _normalizar(formato.info_video(v["url"]), rotulo)
                    v.update({k: x for k, x in completo.items() if x})
                except Exception:
                    pass

            if v["duracao"] is None or v["duracao"] > DURACAO_MAX:
                continue

            assinatura = visual.assinatura_url(v["thumb"]) if perfil["assinaturas_visuais"] else None
            v["nota"], v["motivos"] = formato.pontuar(v, perfil, assinatura)
            if v["nota"] >= NOTA_MINIMA:
                aprovados.append(v)
                log(f"   ✅ {v['nota']:.0%}  {v['duracao']:.0f}s  {v['url']}")
                if len(aprovados) >= alvo:
                    break

    # Primeiro pega os mais parecidos, depois organiza como o usuário pediu
    aprovados.sort(key=ORDENS["formato"][1])
    escolhidos = aprovados[:quantidade]
    escolhidos.sort(key=ORDENS[ordem][1])
    for v in escolhidos:
        v.pop("thumb", None)
    return escolhidos


if __name__ == "__main__":
    nome = sys.argv[1] if len(sys.argv) > 1 else "Ruiva com Sardas"
    qtd = sys.argv[2] if len(sys.argv) > 2 else MAX_LINKS
    for i, v in enumerate(cacar_videos(nome, qtd), 1):
        print(f"{i}. [{v['nota']:.0%} | {v['duracao']:.0f}s] {v['url']}  ({v['fonte']})")
