# -*- coding: utf-8 -*-

import os
import json
import glob
import time
import threading
import xbmc
import xbmcvfs
import xbmcaddon
from urllib.request import urlopen, Request
from contextlib import closing

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
SCRAPERS_PATH = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "resources", "lib", "scrapers"))
LIB_PATH = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "resources", "lib"))
RESOURCES_PATH = xbmcvfs.translatePath(os.path.join(ADDON_PATH, "resources"))
LOCAL_VERSION = os.path.join(SCRAPERS_PATH, ".update")
LAST_CHECK_FILE = os.path.join(SCRAPERS_PATH, ".last_check")
CHECK_INTERVAL = 24 * 60 * 60
BRANCH = "main"
BASE_URL = f"https://raw.githubusercontent.com/icarok99-alt/plugin.video.thethunder/{BRANCH}/"
REMOTE_VERSION_URL = BASE_URL + "last_update.txt"
RAW_SCRAPERS = BASE_URL + "resources/lib/scrapers/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

ADDITIONAL_FILES = [
    {"remote": "resources/lib/sources.py", "local": os.path.join(LIB_PATH, "sources.py")},
    {"remote": "resources/settings.xml", "local": os.path.join(RESOURCES_PATH, "settings.xml")},
]


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[TheThunder AutoUpdate] {msg}", level)


def log_debug(msg):
    xbmc.log(f"[TheThunder AutoUpdate] {msg}", xbmc.LOGDEBUG)


def _read_last_check():
    try:
        if xbmcvfs.exists(LAST_CHECK_FILE):
            with open(LAST_CHECK_FILE, "r", encoding="utf-8") as f:
                return float(f.read().strip())
    except Exception:
        pass
    return 0.0


def _save_last_check():
    try:
        with open(LAST_CHECK_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception as e:
        log_debug(f"Erro ao salvar timestamp: {e}")


def _cooldown_active():
    elapsed = time.time() - _read_last_check()
    if elapsed < CHECK_INTERVAL:
        log_debug(f"Checagem ignorada — próxima em {int((CHECK_INTERVAL - elapsed) / 60)} min")
        return True
    return False


def http_get(url, binary=False):
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with closing(urlopen(req, timeout=15)) as r:
            data = r.read()
            if binary:
                return data
            return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()
    except Exception as e:
        log_debug(f"Erro ao baixar {url}: {e}")
        return None


def get_local_version():
    if not xbmcvfs.exists(LOCAL_VERSION):
        return None
    try:
        with open(LOCAL_VERSION, "r", encoding="utf-8") as f:
            content = f.read().replace("\r\n", "\n").replace("\r", "\n").strip()
            return content if content else None
    except Exception:
        return None


def save_local_version(ver):
    try:
        with open(LOCAL_VERSION, "w", encoding="utf-8", newline="\n") as f:
            f.write(ver + "\n")
    except Exception as e:
        log(f"Erro ao salvar versão local: {e}", xbmc.LOGERROR)


def get_remote_version():
    version = http_get(REMOTE_VERSION_URL)
    log_debug(f"Versão remota: {version}" if version else "Não foi possível obter versão remota")
    return version


def list_remote_scrapers():
    tree_url = f"https://api.github.com/repos/icarok99-alt/plugin.video.thethunder/git/trees/{BRANCH}?recursive=1"
    tree = http_get(tree_url)
    if not tree:
        return []
    try:
        data = json.loads(tree)
        return [
            os.path.basename(item["path"])
            for item in data.get("tree", [])
            if item["path"].startswith("resources/lib/scrapers/")
            and item["type"] == "blob"
            and os.path.basename(item["path"]) not in ["__init__.py", ".update"]
        ]
    except Exception as e:
        log_debug(f"Erro ao listar scrapers remotos: {e}")
        return []


def _do_update():
    if _cooldown_active():
        return

    _save_last_check()

    remote_version = get_remote_version()
    if remote_version is None:
        return

    local_version = get_local_version()

    if local_version is None:
        log("Primeira instalação detectada — registrando versão atual")
        save_local_version(remote_version)
        return

    if local_version == remote_version:
        log_debug("Addon já está na versão mais recente")
        return

    log(f"Atualização disponível: {local_version} → {remote_version}")

    updated = 0
    remote_scrapers = list_remote_scrapers()

    if not remote_scrapers:
        log("Aviso: não foi possível listar scrapers do repositório")

    local_scrapers = [
        os.path.basename(f) for f in glob.glob(os.path.join(SCRAPERS_PATH, "*.py"))
        if os.path.basename(f) not in ["__init__.py", ".update"]
    ]

    for fname in remote_scrapers:
        content = http_get(f"{RAW_SCRAPERS}{fname}", binary=True)
        if content is not None:
            try:
                with open(os.path.join(SCRAPERS_PATH, fname), "wb") as f:
                    f.write(content)
                updated += 1
                log_debug(f"Scraper atualizado: {fname}")
                if fname in local_scrapers:
                    local_scrapers.remove(fname)
            except Exception as e:
                log(f"Erro ao salvar scraper {fname}: {e}", xbmc.LOGERROR)

    for fname in local_scrapers:
        try:
            os.remove(os.path.join(SCRAPERS_PATH, fname))
            log_debug(f"Scraper removido: {fname}")
            updated += 1
        except Exception as e:
            log(f"Erro ao remover scraper {fname}: {e}", xbmc.LOGERROR)

    for file in ADDITIONAL_FILES:
        content = http_get(BASE_URL + file["remote"], binary=True)
        if content is not None:
            try:
                with open(file["local"], "wb") as f:
                    f.write(content)
                updated += 1
                log_debug(f"Arquivo atualizado: {os.path.basename(file['remote'])}")
            except Exception as e:
                log(f"Erro ao atualizar {os.path.basename(file['remote'])}: {e}", xbmc.LOGERROR)

    save_local_version(remote_version)
    log(f"Atualização concluída! {updated} arquivo(s) alterado(s)")


def auto_update():
    threading.Thread(target=_do_update, daemon=True).start()


if __name__ == "__main__":
    _do_update()
