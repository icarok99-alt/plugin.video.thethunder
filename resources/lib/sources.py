# -*- coding: utf-8 -*-

import os
import re
import threading

try:
    from resources.lib.autotranslate import AutoTranslate
except:
    pass

addonId = 'plugin.video.thethunder'

try:
    from kodi_six import xbmcvfs
    scrapers_path = xbmcvfs.translatePath(f'special://home/addons/{addonId}/resources/lib/scrapers/')
except:
    scrapers_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scrapers')

try:
    import xbmcaddon
    addon_instance = xbmcaddon.Addon(id=addonId)
except:
    addon_instance = None


ANIME_SOURCES = {'animesup', 'animesdigital', 'hinatasoul'}
NON_ANIME_SOURCES = {'assistirbiz', 'cinevibehd', 'goflix', 'netcine', 'overflix'}

SCRAPER_SETTINGS = {
    'assistirbiz': 'source_assistirbiz',
    'animesup': 'source_animesup',
    'animesdigital': 'source_animesdigital',
    'cinevibehd': 'source_cinevibehd',
    'goflix': 'source_goflix',
    'hinatasoul': 'source_hinatasoul',
    'netcine': 'source_netcine',
    'overflix': 'source_overflix',
}

_imported_modules = None
_import_lock = threading.Lock()

def _import_modules():
    global _imported_modules
    if _imported_modules is not None:
        return _imported_modules
    with _import_lock:
        if _imported_modules is not None:
            return _imported_modules
        modulos = []
        pasta = scrapers_path
        if not pasta or not os.path.isdir(pasta):
            _imported_modules = []
            return _imported_modules
        for fname in os.listdir(pasta):
            if not fname.endswith('.py') or fname == '__init__.py':
                continue
            script = fname[:-3]
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(script, os.path.join(pasta, fname))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                modulos.append(mod)
            except Exception:
                pass
        _imported_modules = modulos
    return _imported_modules

def _load_modules():
    result = []
    for mod in _import_modules():
        script = mod.__name__
        if addon_instance:
            setting_key = SCRAPER_SETTINGS.get(script)
            if setting_key:
                try:
                    if addon_instance.getSetting(setting_key) != 'true':
                        continue
                except:
                    pass
        result.append(mod)
    return result

def get_anime_scrapers():
    return [m for m in _load_modules() if m.__name__ in ANIME_SOURCES]

def get_non_anime_scrapers():
    return [m for m in _load_modules() if m.__name__ in NON_ANIME_SOURCES]

def _run_parallel(scrapers_list, method_name, method_args):
    results = []
    lock = threading.Lock()

    def _worker(modulo):
        try:
            fn = getattr(modulo.source, method_name, None)
            if fn is None:
                return
            r = fn(*method_args)
            if r:
                with lock:
                    results.extend(r)
        except Exception:
            pass

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_worker, m) for m in scrapers_list]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass

    seen = set()
    flat = []
    for item in results:
        try:
            name, url = item[0], item[1]
            if url not in seen:
                seen.add(url)
                flat.append((name, url))
        except:
            pass

    return flat

def movie_content(tmdb_id, year, movie_name, original_name):
    return _run_parallel(get_non_anime_scrapers(), 'search_movies', (tmdb_id, year, movie_name, original_name))

def show_content(tmdb_id, season, episode, serie_name, original_name):
    return _run_parallel(get_non_anime_scrapers(), 'search_tvshows', (tmdb_id, season, episode, serie_name, original_name))

def search_movies(tmdb_id, year, movie_name, original_name):
    return movie_content(tmdb_id, year, movie_name, original_name)

def search_tvshows(tmdb_id, season, episode, serie_name, original_name):
    return show_content(tmdb_id, season, episode, serie_name, original_name)

def show_content_anime(mal_id, episode, anime_name, original_name, year=None):
    return _run_parallel(get_anime_scrapers(), 'search_animes', (mal_id, episode, anime_name, original_name, year))

def movie_content_anime(mal_id, anime_name, original_name, year=None):
    return _run_parallel(get_anime_scrapers(), 'search_animes', (mal_id, None, anime_name, original_name, year))

def search_anime_episodes(mal_id, episode, anime_name, original_name, year=None):
    return show_content_anime(mal_id, episode, anime_name, original_name, year)

def search_anime_movies(mal_id, anime_name, original_name, year=None):
    return movie_content_anime(mal_id, anime_name, original_name, year)

def resolver_global(scrapers_list, method_name, url):
    stream = ''
    sub = ''
    for modulo in scrapers_list:
        try:
            fn = getattr(modulo.source, method_name, None)
            if fn is None:
                continue
            result = fn(url)
            if result and len(result) > 0 and result[0]:
                stream = result[0][0] if len(result[0]) > 0 else ''
                sub = result[0][1] if len(result[0]) > 1 else ''
                if stream:
                    break
        except:
            continue
    return stream, sub

def resolve_movies(url):
    return resolver_global(get_non_anime_scrapers(), 'resolve_movies', url)

def resolve_tvshows(url):
    return resolver_global(get_non_anime_scrapers(), 'resolve_tvshows', url)

def resolve_animes(url):
    return resolver_global(get_anime_scrapers(), 'resolve_animes', url)

def resolve_anime_movies(url):
    return resolver_global(get_anime_scrapers(), 'resolve_animes_movies', url)
