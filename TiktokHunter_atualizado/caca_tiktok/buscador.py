"""
Caçador de vídeos no TikTok POR FORMATO.

Como funciona:
  1. Abre os links de exemplo do nicho (exemplos.json) e aprende o formato
     (som, legenda, hashtags, criadores, duração e aparência) -> formato.py
  2. Junta candidatos de onde esse formato aparece:
       - vídeos que usam o mesmo som dos exemplos
       - a busca do TikTok com as palavras e hashtags do formato
       - as hashtags que os PRÓPRIOS exemplos usam (descobertas sozinhas)
       - outros vídeos dos criadores dos exemplos (menos os ignorados)
       - PERFIS NOVOS: quando acha um vídeo bem parecido de alguém que não
         está nos exemplos, abre o perfil dessa pessoa e procura mais lá
  3. Dá uma nota de compatibilidade para cada candidato de até DURACAO_MAX
     segundos e devolve no máximo 4 links, organizados como pedido.

Uso no terminal:
    python buscador.py "Ruiva com Sardas" 4
"""

import sys
from collections import deque
from urllib.parse import quote

import coletor
import formato
import visual
from nichos import obter_nicho

DURACAO_MAX = 18        # segundos
MAX_LINKS = 4           # limite de links por pedido
VIDEOS_POR_FONTE = 40   # quantos vídeos olhar em cada criador/hashtag
TOP_HASHTAGS = 6        # quantas hashtags aprendidas usar como fonte
MAX_DETALHES = 80       # limite de vídeos abertos um a um (deixa a busca mais rápida)
NOTA_MINIMA = 0.20      # abaixo disso o vídeo não é considerado do mesmo formato
BUSCAR_NOS_CRIADORES = True   # também olha os perfis dos exemplos (os não ignorados)

# Perfis novos (fora dos exemplos)
DESCOBRIR_PERFIS = True       # abre o perfil de quem postou um vídeo bem parecido
NOTA_PERFIL_NOVO = 0.35       # nota mínima do vídeo para valer a pena abrir o perfil
MAX_PERFIS_NOVOS = 6          # quantos perfis novos abrir por busca
MAX_POR_AUTOR = 2             # no máximo X vídeos do mesmo perfil no resultado
BUSCAS_POR_TEXTO = 2          # quantas pesquisas no campo de busca do TikTok

# Contas que nunca entram nos resultados nem são usadas como fonte
AUTORES_IGNORADOS = {"infinity_achados", "my.lar_", "clicanocarrinho"}

ORDENS = {
    "formato": ("Mais parecidos com o formato", lambda v: -v["nota"]),
    "views": ("Mais vistos", lambda v: -(v["views"] or 0)),
    "curtidas": ("Mais curtidos", lambda v: -(v["curtidas"] or 0)),
    "recentes": ("Mais recentes", lambda v: -(v["data"] or 0)),
    "curtos": ("Mais curtos", lambda v: v["duracao"]),
}


def _listar(url, limite):
    """Lista vídeos de uma página (som, perfil ou hashtag) sem abrir cada um."""
    return coletor.listar(url, limite)


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
        "music_id": e.get("music_id"),
        "duracao": e.get("duration") or None,
        "views": e.get("view_count"),
        "curtidas": e.get("like_count"),
        "data": e.get("timestamp"),
        "thumb": e.get("thumbnail"),
        "fonte": fonte,
    }


def _fontes_iniciais(perfil):
    fontes = []
    # 1º) vídeos que usam o MESMO som dos exemplos — o sinal mais forte de formato
    for mid in perfil.get("musicas", {}):
        fontes.append(("som do exemplo", f"https://www.tiktok.com/music/som-{mid}"))
    # 2º) a busca do TikTok, que traz vídeos de perfis que ninguém conhece ainda
    termos = []
    palavras = list(perfil["palavras"])[:3]
    if palavras:
        termos.append(" ".join(palavras))
    termos += list(perfil["hashtags"])[:BUSCAS_POR_TEXTO]
    for termo in list(dict.fromkeys(termos))[:BUSCAS_POR_TEXTO]:
        fontes.append((f"busca '{termo}'", f"https://www.tiktok.com/search/video?q={quote(termo)}"))
    # 3º) hashtags dos exemplos
    for tag in list(perfil["hashtags"])[:TOP_HASHTAGS]:
        fontes.append((f"#{tag}", f"https://www.tiktok.com/tag/{tag}"))
    # 4º) perfis dos exemplos que não estão na lista de ignorados
    if BUSCAR_NOS_CRIADORES:
        for autor in perfil["autores"]:
            if autor not in AUTORES_IGNORADOS:
                fontes.append((f"@{autor}", f"https://www.tiktok.com/@{autor}"))
    return fontes


def cacar_videos(nome_nicho, quantidade=MAX_LINKS, ordem="formato", log=print):
    with coletor.sessao(log):
        return _cacar(nome_nicho, quantidade, ordem, log)


def _cacar(nome_nicho, quantidade, ordem, log):
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
    fila = deque(_fontes_iniciais(perfil))
    perfis_abertos = set(perfil["autores"]) | AUTORES_IGNORADOS
    perfis_novos = 0

    while fila:
        if len(aprovados) >= alvo:
            break
        rotulo, url = fila.popleft()
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
                # Perfil novo com vídeo bem parecido: entra na fila para ser explorado
                if (DESCOBRIR_PERFIS and v["autor"] and v["autor"] not in perfis_abertos
                        and v["nota"] >= NOTA_PERFIL_NOVO and perfis_novos < MAX_PERFIS_NOVOS):
                    perfis_abertos.add(v["autor"])
                    perfis_novos += 1
                    fila.appendleft((f"@{v['autor']} (perfil novo)", f"https://www.tiktok.com/@{v['autor']}"))
                    log(f"   👤 perfil novo descoberto: @{v['autor']}")
                if len(aprovados) >= alvo:
                    break

    # Primeiro pega os mais parecidos, depois organiza como o usuário pediu
    aprovados.sort(key=ORDENS["formato"][1])
    escolhidos, por_autor = [], {}
    for v in aprovados:  # variedade: no máximo MAX_POR_AUTOR vídeos de cada perfil
        if por_autor.get(v["autor"], 0) < MAX_POR_AUTOR:
            escolhidos.append(v)
            por_autor[v["autor"]] = por_autor.get(v["autor"], 0) + 1
        if len(escolhidos) == quantidade:
            break
    escolhidos.sort(key=ORDENS[ordem][1])
    for v in escolhidos:
        v.pop("thumb", None)
    return escolhidos


if __name__ == "__main__":
    nome = sys.argv[1] if len(sys.argv) > 1 else "Ruiva com Sardas"
    qtd = sys.argv[2] if len(sys.argv) > 2 else MAX_LINKS
    for i, v in enumerate(cacar_videos(nome, qtd), 1):
        print(f"{i}. [{v['nota']:.0%} | {v['duracao']:.0f}s] {v['url']}  ({v['fonte']})")
