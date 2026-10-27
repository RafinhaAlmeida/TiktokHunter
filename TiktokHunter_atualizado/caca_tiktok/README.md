# Caçador de TikTok (por formato)

Você dá 2 ou mais links de exemplo por nicho. O programa aprende o **formato** desses vídeos e caça vídeos parecidos de **até 18 segundos**, devolvendo **no máximo 4 links**.

## Como rodar
```bash
pip install -r requirements.txt
python app.py          # abre em http://127.0.0.1:5000
```
Terminal: `python buscador.py "Ruiva com Sardas" 4`

## Se não achar vídeos
O programa agora abre o TikTok num **Chrome de verdade** (Playwright), que o TikTok bloqueia bem menos que o yt-dlp.
Uma janela do Chrome abre durante a busca. Se aparecer captcha, resolva nela, e o programa espera.
Se o Chrome não abrir: `python -m playwright install chromium`. Ajustes em `coletor.py` (`MOTOR`, `MOSTRAR_NAVEGADOR`).

## Como ele entende o formato
Abre cada exemplo e guarda:
- **som** usado (vídeos do mesmo formato costumam usar o mesmo áudio)
- **hashtags e palavras** da legenda
- **criadores** que postam esse formato
- **duração** e **aparência** da capa (visual.py)

Depois procura em várias fontes, nesta ordem:
1. vídeos que usam o **mesmo som** dos exemplos
2. a **busca do TikTok** com as palavras e hashtags do formato
3. as **hashtags** dos exemplos
4. os perfis dos exemplos que não estão em `AUTORES_IGNORADOS`

Quando acha um vídeo bem parecido de um **perfil novo**, abre esse perfil e procura mais lá (até `MAX_PERFIS_NOVOS`). Cada vídeo recebe uma nota de 0–100% e o resultado traz no máximo `MAX_POR_AUTOR` vídeos de cada perfil.

## Arquivos
- `exemplos.json` – links de exemplo de cada nicho (também editável pela página).
- `formato.py` – aprende o formato e calcula a nota. Pesos em `PESOS`.
- `visual.py` + `clip_numpy.py` – comparam as capas com o modelo CLIP (sem torch, funciona no Python 3.15).
- `coletor.py` – lê o TikTok pelo Chrome (Playwright), com yt-dlp de reserva.
- `buscador.py` – busca. Ajustes no topo: `DURACAO_MAX`, `NOTA_MINIMA`, `AUTORES_IGNORADOS`, `DESCOBRIR_PERFIS`, `MAX_PERFIS_NOVOS`, `MAX_POR_AUTOR`.
- `personas.py`, `nichos.py`, `app.py`, `templates/index.html`.

## Dicas
- Quanto mais exemplos (3–5), melhor ele entende o formato.
- Se vier pouca coisa, baixe `NOTA_MINIMA` (ex.: 0.12).
- Mudou os exemplos? Clique em **Reaprender**.
- Se nada abrir: `pip install -U "yt-dlp[default,curl-cffi]"`.
