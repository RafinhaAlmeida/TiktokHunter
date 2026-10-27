"""
Front-end básico (Flask) do Caçador de TikTok por formato.

Rodar:
    pip install -r requirements.txt
    python app.py
Depois abra http://127.0.0.1:5000
"""

from flask import Flask, jsonify, render_template, request

import coletor
import formato
from buscador import DURACAO_MAX, MAX_LINKS, ORDENS, cacar_videos
from nichos import listar_nichos, obter_nicho, salvar_exemplos

app = Flask(__name__)


@app.get("/")
def index():
    return render_template(
        "index.html",
        nichos=listar_nichos(),
        ordens={k: v[0] for k, v in ORDENS.items()},
        max_links=MAX_LINKS,
        duracao_max=DURACAO_MAX,
    )


@app.post("/exemplos")
def exemplos():
    d = request.get_json(force=True)
    links = salvar_exemplos(d["nicho"], d.get("links", []))
    return jsonify(ok=True, links=links)


@app.post("/formato")
def ver_formato():
    d = request.get_json(force=True)
    nicho = obter_nicho(d["nicho"])
    log = []
    try:
        with coletor.sessao(log.append):
            perfil = formato.aprender_formato(nicho["exemplos"], log=log.append,
                                              usar_cache=not d.get("reaprender"))
        return jsonify(ok=True, formato=formato.resumo(perfil), log=log)
    except Exception as erro:
        return jsonify(ok=False, erro=str(erro), log=log), 400


@app.post("/buscar")
def buscar():
    d = request.get_json(force=True)
    log = []
    try:
        videos = cacar_videos(d.get("nicho"), d.get("quantidade", MAX_LINKS),
                              d.get("ordem", "formato"), log=log.append)
        return jsonify(ok=True, videos=videos, log=log)
    except Exception as erro:
        return jsonify(ok=False, erro=str(erro), log=log), 400


if __name__ == "__main__":
    app.run(debug=True)
