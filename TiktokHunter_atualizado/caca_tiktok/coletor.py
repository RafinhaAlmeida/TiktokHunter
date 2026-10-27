"""
Coletor: de onde vêm os dados dos vídeos.

Dois motores:
  - "navegador": abre o TikTok num Chrome de verdade (Playwright) e lê os
    dados que o próprio site carrega. É o mais confiável, porque o TikTok
    vê um navegador normal. Precisa de:
        pip install playwright
    (usa o Google Chrome que já está instalado; se não achar, rode
     `python -m playwright install chromium`)
  - "ytdlp": o método antigo, sem janela. O TikTok bloqueia com frequência.

No modo "auto" tenta o navegador primeiro e cai no yt-dlp se falhar.
Nenhum vídeo é baixado: os arquivos de vídeo são bloqueados no navegador.
"""

import contextlib
import json
import os
import threading

import yt_dlp

MOTOR = "auto"            # "auto", "navegador" ou "ytdlp"
MOSTRAR_NAVEGADOR = True  # janela visível: o TikTok bloqueia menos e você pode resolver captcha
ESPERA_CAPTCHA = 90       # segundos que o programa espera você resolver um captcha
PASTA_PERFIL = os.path.join(os.path.expanduser("~"), ".cache", "caca_tiktok", "navegador")

YDL = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}
_local = threading.local()


def _num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def converter_item(item):
    """Converte o JSON do TikTok para o mesmo formato de dicionário do yt-dlp."""
    autor = item.get("author") or {}
    autor = autor.get("uniqueId") if isinstance(autor, dict) else str(autor)
    musica = item.get("music") or {}
    video = item.get("video") or {}
    stats = item.get("statsV2") or item.get("stats") or {}
    vid = str(item.get("id"))
    return {
        "id": vid,
        "description": item.get("desc") or "",
        "duration": video.get("duration") or None,
        "track": musica.get("title"),
        "artist": musica.get("authorName"),
        "music_id": str(musica["id"]) if musica.get("id") else None,
        "uploader": autor,
        "view_count": _num(stats.get("playCount")),
        "like_count": _num(stats.get("diggCount")),
        "timestamp": _num(item.get("createTime")),
        "thumbnail": video.get("cover") or video.get("originCover") or video.get("dynamicCover"),
        "webpage_url": f"https://www.tiktok.com/@{autor}/video/{vid}",
    }


class Navegador:
    def __init__(self, log=print):
        from playwright.sync_api import sync_playwright

        self.log = log
        self._pw = sync_playwright().start()
        os.makedirs(PASTA_PERFIL, exist_ok=True)
        opcoes = dict(user_data_dir=PASTA_PERFIL, headless=not MOSTRAR_NAVEGADOR,
                      viewport={"width": 1280, "height": 900}, locale="pt-BR",
                      args=["--mute-audio", "--disable-blink-features=AutomationControlled"])
        try:
            self.ctx = self._pw.chromium.launch_persistent_context(channel="chrome", **opcoes)
        except Exception:
            self.ctx = self._pw.chromium.launch_persistent_context(**opcoes)
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        # Não baixa vídeo nenhum: bloqueia arquivos de mídia
        self.page.route("**/*", lambda r: r.abort() if r.request.resource_type == "media" else r.continue_())

    def fechar(self):
        for f in (self.ctx.close, self._pw.stop):
            try:
                f()
            except Exception:
                pass

    def _esperar_captcha(self):
        seletor = "[id*='captcha'], [class*='captcha'], [class*='Captcha']"
        if self.page.locator(seletor).count() == 0:
            return
        self.log(f"🧩 O TikTok pediu um captcha. Resolva na janela do Chrome (espero {ESPERA_CAPTCHA}s)...")
        for _ in range(ESPERA_CAPTCHA):
            self.page.wait_for_timeout(1000)
            if self.page.locator(seletor).count() == 0:
                self.log("   captcha resolvido 👍")
                return

    def info_video(self, url):
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        self._esperar_captcha()
        bruto = self.page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__").text_content(timeout=20000)
        dados = json.loads(bruto)["__DEFAULT_SCOPE__"]
        item = dados["webapp.video-detail"]["itemInfo"]["itemStruct"]
        return converter_item(item)

    def listar(self, url, limite):
        itens = {}

        def ao_receber(resp):
            u = resp.url
            if "/api/" not in u or not any(p in u for p in ("item_list", "/search/", "/recommend/")):
                return
            try:
                d = resp.json()
            except Exception:
                return
            lista = d.get("itemList") or d.get("item_list") or d.get("items") or [
                x.get("item") for x in d.get("data") or [] if isinstance(x, dict) and x.get("item")]
            for it in lista or []:
                if isinstance(it, dict) and it.get("id"):
                    itens.setdefault(str(it["id"]), it)

        self.page.on("response", ao_receber)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.page.wait_for_timeout(2500)
            self._esperar_captcha()
            parado = 0
            for _ in range(20):
                if len(itens) >= limite:
                    break
                antes = len(itens)
                self.page.mouse.wheel(0, 5000)
                self.page.wait_for_timeout(1800)
                parado = parado + 1 if len(itens) == antes else 0
                if parado >= 4:
                    break
        finally:
            self.page.remove_listener("response", ao_receber)
        return [converter_item(i) for i in list(itens.values())[:limite]]


def _tem_playwright():
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except Exception:
        return False


@contextlib.contextmanager
def sessao(log=print):
    """Abre o navegador uma vez para a busca inteira e fecha no final."""
    nav = None
    if MOTOR in ("auto", "navegador"):
        if _tem_playwright():
            try:
                nav = Navegador(log)
                log("🌐 Usando o Chrome (Playwright) para ler o TikTok.")
            except Exception as erro:
                log(f"⚠️ O Chrome não abriu ({erro}). Usando yt-dlp.")
        else:
            log("ℹ️ Playwright não instalado (pip install playwright). Usando yt-dlp.")
    _local.nav, _local.log = nav, log
    try:
        yield
    finally:
        _local.nav = None
        if nav:
            nav.fechar()


def info_video(url):
    nav, log = getattr(_local, "nav", None), getattr(_local, "log", print)
    if nav:
        try:
            info = nav.info_video(url)
            if info.get("id"):
                return info
        except Exception as erro:
            log(f"   (navegador falhou neste vídeo: {str(erro)[:100]})")
        if MOTOR == "navegador":
            return {}
    with yt_dlp.YoutubeDL(YDL) as ydl:
        return ydl.extract_info(url, download=False) or {}


def listar(url, limite):
    nav, log = getattr(_local, "nav", None), getattr(_local, "log", print)
    if nav:
        try:
            itens = nav.listar(url, limite)
            if itens:
                return itens
            log("   (navegador não encontrou vídeos nesta página)")
        except Exception as erro:
            log(f"   (navegador falhou nesta página: {str(erro)[:100]})")
        if MOTOR == "navegador":
            return []
    opts = dict(YDL, extract_flat="in_playlist", playlistend=limite)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return [e for e in (info or {}).get("entries") or [] if e]
