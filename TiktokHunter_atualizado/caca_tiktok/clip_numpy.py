"""
CLIP (ViT-B/32) rodando SÓ com numpy — sem torch, sem onnxruntime.

Feito para funcionar em versões novas do Python (ex.: 3.15), em que o
torch ainda não tem instalador. Faz a mesma conta do CLIP original para
transformar uma imagem num vetor que "entende" o conteúdo dela.

Precisa de:  pip install numpy safetensors
Na primeira vez baixa os pesos oficiais da OpenAI (~600 MB) do Hugging Face
e guarda em ~/.cache/caca_tiktok/. Depois funciona offline.
"""

import os
import urllib.request

import numpy as np
from PIL import Image

URL_PESOS = "https://huggingface.co/openai/clip-vit-base-patch32/resolve/main/model.safetensors"
PASTA_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "caca_tiktok")
ARQ_PESOS = os.path.join(PASTA_CACHE, "clip-vit-base-patch32.safetensors")

MEDIA = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
DESVIO = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)


def baixar_pesos(log=print):
    if os.path.exists(ARQ_PESOS):
        return ARQ_PESOS
    os.makedirs(PASTA_CACHE, exist_ok=True)
    temp = ARQ_PESOS + ".parcial"
    log("⬇️ Baixando pesos do CLIP (~600 MB, só na primeira vez)...")

    def progresso(blocos, tam_bloco, total):
        if total > 0 and blocos % 500 == 0:
            log(f"   {min(100, blocos * tam_bloco * 100 // total)}%")

    urllib.request.urlretrieve(URL_PESOS, temp, progresso)
    os.replace(temp, ARQ_PESOS)
    return ARQ_PESOS


def _layer_norm(x, w, b, eps=1e-5):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / np.sqrt(v + eps) * w + b


def _softmax(x):
    x = x - x.max(-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(-1, keepdims=True)


class ClipVisual:
    def __init__(self, caminho=None):
        from safetensors import safe_open

        caminho = caminho or baixar_pesos()
        self.p = {}
        with safe_open(caminho, framework="numpy") as f:
            for k in f.keys():
                if k.startswith("vision_model.") or k == "visual_projection.weight":
                    self.p[k] = f.get_tensor(k).astype(np.float32)

        pe = self.p["vision_model.embeddings.patch_embedding.weight"]  # [D, 3, P, P]
        self.dim, _, self.patch, _ = pe.shape
        self.patch_w = pe.reshape(self.dim, -1).T                       # [3*P*P, D]
        self.n_camadas = len({k.split(".")[3] for k in self.p if ".encoder.layers." in k})
        self.cabecas = self.dim // 64
        n_pos = self.p["vision_model.embeddings.position_embedding.weight"].shape[0]
        self.tamanho = int(round((n_pos - 1) ** 0.5)) * self.patch     # 224

    def preparar(self, img):
        """Redimensiona, corta o centro e normaliza como o CLIP original."""
        img = img.convert("RGB")
        w, h = img.size
        escala = self.tamanho / min(w, h)
        img = img.resize((max(self.tamanho, round(w * escala)), max(self.tamanho, round(h * escala))),
                         Image.BICUBIC)
        w, h = img.size
        esq, topo = (w - self.tamanho) // 2, (h - self.tamanho) // 2
        img = img.crop((esq, topo, esq + self.tamanho, topo + self.tamanho))
        x = np.asarray(img, dtype=np.float32) / 255.0
        return ((x - MEDIA) / DESVIO).transpose(2, 0, 1)                # [3, H, W]

    def vetor_pixels(self, x):
        """x: [3, H, W] já normalizado -> vetor de imagem do CLIP (não normalizado)."""
        p, P = self.p, self.patch
        g = self.tamanho // P
        # Divide em patches 32x32 e projeta (equivale à convolução do ViT)
        patches = x.reshape(3, g, P, g, P).transpose(1, 3, 0, 2, 4).reshape(g * g, -1)
        h = patches @ self.patch_w
        cls = p["vision_model.embeddings.class_embedding"][None]
        h = np.concatenate([cls, h]) + p["vision_model.embeddings.position_embedding.weight"]
        h = _layer_norm(h, p["vision_model.pre_layrnorm.weight"], p["vision_model.pre_layrnorm.bias"])

        n, d, H = h.shape[0], self.dim, self.cabecas
        for i in range(self.n_camadas):
            c = f"vision_model.encoder.layers.{i}."
            lin = lambda t, nome: t @ p[c + nome + ".weight"].T + p[c + nome + ".bias"]

            r = h
            t = _layer_norm(h, p[c + "layer_norm1.weight"], p[c + "layer_norm1.bias"])
            q = lin(t, "self_attn.q_proj").reshape(n, H, -1).transpose(1, 0, 2)
            k = lin(t, "self_attn.k_proj").reshape(n, H, -1).transpose(1, 0, 2)
            v = lin(t, "self_attn.v_proj").reshape(n, H, -1).transpose(1, 0, 2)
            att = _softmax(q @ k.transpose(0, 2, 1) / np.sqrt(d // H))
            t = (att @ v).transpose(1, 0, 2).reshape(n, d)
            h = r + lin(t, "self_attn.out_proj")

            r = h
            t = _layer_norm(h, p[c + "layer_norm2.weight"], p[c + "layer_norm2.bias"])
            t = lin(t, "mlp.fc1")
            t = t / (1 + np.exp(-1.702 * t))                              # quick_gelu
            h = r + lin(t, "mlp.fc2")

        cls = _layer_norm(h[0], p["vision_model.post_layernorm.weight"], p["vision_model.post_layernorm.bias"])
        return cls @ p["visual_projection.weight"].T

    def vetor(self, img):
        """PIL.Image -> vetor de 512 números que descreve o conteúdo da imagem."""
        return self.vetor_pixels(self.preparar(img))
