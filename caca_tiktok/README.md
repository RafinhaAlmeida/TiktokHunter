# Caçador de TikTok (por formato)

Você dá 2 ou mais links de exemplo por nicho. O programa aprende o **formato** desses vídeos e caça vídeos parecidos de **até 18 segundos**, devolvendo **no máximo 4 links**.

## Como rodar
```bash
pip install -r requirements.txt
python app.py          # abre em http://127.0.0.1:5000
```
Terminal: `python buscador.py "Ruiva com Sardas" 4`

## Como ele entende o formato
Abre cada exemplo e guarda:
- **som** usado (vídeos do mesmo formato costumam usar o mesmo áudio)
- **hashtags e palavras** da legenda
- **criadores** que postam esse formato
- **duração** e **aparência** da capa (visual.py)

Depois busca nos perfis desses criadores e nas hashtags que os exemplos usam, dá uma nota de 0–100% para cada vídeo e fica com os mais parecidos.

## Arquivos
- `exemplos.json` – links de exemplo de cada nicho (também editável pela página).
- `formato.py` – aprende o formato e calcula a nota. Pesos em `PESOS`.
- `visual.py` – compara as capas. Com `pip install sentence-transformers` passa a usar CLIP, que entende o conteúdo da imagem.
- `buscador.py` – busca. Ajustes no topo: `DURACAO_MAX`, `NOTA_MINIMA`, `AUTORES_IGNORADOS`, `TOP_HASHTAGS`.
- `personas.py`, `nichos.py`, `app.py`, `templates/index.html`.

## Dicas
- Quanto mais exemplos (3–5), melhor ele entende o formato.
- Se vier pouca coisa, baixe `NOTA_MINIMA` (ex.: 0.12).
- Mudou os exemplos? Clique em **Reaprender**.
- Se nada abrir: `pip install -U "yt-dlp[default,curl-cffi]"`.
