#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
from datetime import datetime
import sqlite3

try:
    import xbmc
    import xbmcgui
    import xbmcvfs
    import xbmcaddon
except ImportError:
    xbmc = xbmcgui = xbmcvfs = xbmcaddon = None


def is_kodi():
    return xbmc is not None and xbmcgui is not None

def notify(title, message, duration=3000):
    try:
        if is_kodi():
            xbmcgui.Dialog().notification(title, message, xbmcgui.NOTIFICATION_INFO, duration)
        else:
            print(f"[{title}] {message}")
    except Exception:
        print(f"[{title}] {message}")

def log(msg):
    try:
        if is_kodi():
            xbmc.log(f"[thethunder][cache_manager] {msg}", xbmc.LOGINFO)
        else:
            print(f"[thethunder][cache_manager] {msg}")
    except Exception:
        print(f"[thethunder][cache_manager] {msg}")


def get_profile_dir():
    if is_kodi():
        try:
            addon = xbmcaddon.Addon("plugin.video.thethunder")
            return xbmcvfs.translatePath(addon.getAddonInfo("profile"))
        except Exception:
            pass

    if os.name == "nt":
        base = os.getenv("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Caches")
    else:
        base = os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))

    return os.path.join(base, "thethunder")

def get_db_path():
    return os.path.join(get_profile_dir(), "media.db")


def get_cache_ttl_days():
    try:
        if is_kodi():
            addon = xbmcaddon.Addon("plugin.video.thethunder")
            val = addon.getSetting('cache_ttl_days')
            if val == '':
                return 7
            days = int(val)
            return days if days >= 0 else 7
    except:
        pass
    return 7


def human_readable_size(size_bytes):
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {units[i]}"

def get_cache_size_local():
    db_path = get_db_path()
    if is_kodi() and xbmcvfs.exists(db_path):
        try:
            stat = xbmcvfs.Stat(db_path)
            return stat.st_size()
        except:
            return 0
    elif os.path.exists(db_path):
        try:
            return os.path.getsize(db_path)
        except:
            return 0
    return 0


def clear_cache():
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        notify("TheThunder", "Nenhum cache encontrado")
        log("Banco de dados não encontrado")
        return
    
    deleted = False
    
    try:
        if is_kodi() and xbmcvfs.exists(db_path):
            xbmcvfs.delete(db_path)
            deleted = True
            log("Arquivo media.db deletado via xbmcvfs")
        elif os.path.exists(db_path):
            os.remove(db_path)
            deleted = True
            log("Arquivo media.db deletado via os.remove")
        
        wal_file = db_path + '-wal'
        shm_file = db_path + '-shm'
        
        if is_kodi():
            if xbmcvfs.exists(wal_file):
                xbmcvfs.delete(wal_file)
            if xbmcvfs.exists(shm_file):
                xbmcvfs.delete(shm_file)
        else:
            if os.path.exists(wal_file):
                os.remove(wal_file)
            if os.path.exists(shm_file):
                os.remove(shm_file)
        
    except Exception as e:
        log(f"Erro ao deletar arquivo: {e}")
        notify("TheThunder", f"Erro ao deletar: {e}")
        return
    
    notify("TheThunder", "Cache limpo com sucesso!" if deleted else "Nenhum cache encontrado")
    log("Cache limpo")

def show_cache():
    size = get_cache_size_local()
    size_str = human_readable_size(size)
    notify("TheThunder", f"Tamanho do cache: {size_str}", 4000)
    log(f"Tamanho do cache: {size_str}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("clear_cache", "--clear-cache", "-c"):
            clear_cache()
        elif arg in ("show_cache", "--show-cache", "-s"):
            show_cache()
    else:
        clear_cache()

def check_auto_expiry():
    db_path = get_db_path()

    if not os.path.exists(db_path):
        return

    ttl_days = get_cache_ttl_days()

    try:
        last_modified = datetime.fromtimestamp(os.path.getmtime(db_path))
    except OSError:
        return

    from datetime import timedelta
    if ttl_days == 0 or datetime.now() - last_modified >= timedelta(days=ttl_days):
        clear_cache()
