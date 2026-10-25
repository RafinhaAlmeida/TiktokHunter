"""
Compara a APARÊNCIA dos vídeos pela miniatura (capa).

Três modos, escolhidos sozinhos (o primeiro disponível):
  - "clip": modelo CLIP via sentence-transformers (precisa de torch).
  - "clip-numpy": o MESMO CLIP rodando só com numpy (clip_numpy.py).
    Funciona no Python 3.15, onde o torch ainda não existe.
        pip install numpy safetensors
    Os dois CLIP entendem o conteúdo da imagem (camisa da seleção,
    chapéu de palha, cabine de avião...). São os mais precisos.
  - "cores": sem nada extra, compara a paleta de cores e a composição da
    miniatura. Mais simples, mas já ajuda (ex.: amarelo/verde da camisa).
"""

import io
import math
import urllib.request

from PIL import Image

MODO = "cores"
_clip = None
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401
    MODO = "clip"
except Exception:
    try:
        import numpy  # noqa: F401
        import safetensors  # noqa: F401
        MODO = "clip-numpy"
    except Exception:
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _baixar_imagem(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.tiktok.com/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def _assinatura_cores(img):
    # Histograma de cores (4x4x4) + miniatura 8x8 em tons de cinza (composição)
    pequena = img.resize((64, 64))
    hist = [0] * 64
    for r, g, b in pequena.getdata():
        hist[(r // 64) * 16 + (g // 64) * 4 + (b // 64)] += 1
    total = sum(hist)
    cores = [h / total for h in hist]
    cinza = list(img.convert("L").resize((8, 8)).getdata())
    media = sum(cinza) / 64
    forma = [(c - media) / 255 for c in cinza]
    return cores + forma


def _assinatura_clip(img):
    global _clip, MODO
    if _clip is None:
        if MODO == "clip":
            from sentence_transformers import SentenceTransformer
            _clip = SentenceTransformer("clip-ViT-B-32").encode
        else:
            try:
                import clip_numpy
                _clip = clip_numpy.ClipVisual().vetor
            except Exception as erro:  # sem internet para baixar os pesos etc.
                print(f"[visual] CLIP numpy indisponível ({erro}); usando modo cores.")
                MODO = "cores"
                return _assinatura_cores(img)
    return [float(x) for x in _clip(img)]


def assinatura_url(url):
    """Assinatura visual da imagem do link, ou None se falhar."""
    if not url:
        return None
    try:
        img = _baixar_imagem(url)
        return _assinatura_cores(img) if MODO == "cores" else _assinatura_clip(img)
    except Exception:
        return None


def similaridade(a, b):
    """0 a 1 — quanto as duas imagens se parecem."""
    if not a or not b or len(a) != len(b):
        return 0.0
    if len(a) != 128:  # vetor do CLIP (o modo cores tem 128 números)
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        cos = dot / (na * nb) if na and nb else 0
        # CLIP dá ~0.5 para imagens sem relação e ~0.9+ para muito parecidas
        return max(0.0, min(1.0, (cos - 0.5) / 0.45))
    cores_a, forma_a = a[:64], a[64:]
    cores_b, forma_b = b[:64], b[64:]
    sim_cores = sum(min(x, y) for x, y in zip(cores_a, cores_b))  # interseção do histograma
    dot = sum(x * y for x, y in zip(forma_a, forma_b))
    na = math.sqrt(sum(x * x for x in forma_a))
    nb = math.sqrt(sum(y * y for y in forma_b))
    sim_forma = (dot / (na * nb) + 1) / 2 if na and nb else 0.5
    return 0.7 * sim_cores + 0.3 * sim_forma
