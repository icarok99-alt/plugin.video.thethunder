# -*- coding: utf-8 -*-

import os
import json
import time
import hashlib
import sqlite3
import threading
import xbmcvfs
import xbmcaddon
from datetime import datetime
from urllib.parse import quote
from contextlib import contextmanager
from resources.lib.helper import requests
from resources.lib.utils import get_current_date
from resources.lib.kodi_service import get_service as get_kodi_service

addon = xbmcaddon.Addon()

def getString(string_id):
    return addon.getLocalizedString(string_id)

TRANSLATE = xbmcvfs.translatePath
profile_dir = TRANSLATE(addon.getAddonInfo('profile'))
db_file = os.path.join(profile_dir, 'media.db')

if not xbmcvfs.exists(profile_dir):
    xbmcvfs.mkdirs(profile_dir)

API_KEY = '92c1507cc18d85290e7a0b96abb37316'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'

_season_cache = {}
_season_cache_lock = threading.Lock()

_db_initialized = False
_db_init_lock = threading.Lock()

def _check_expiry_once():
    from resources.lib.cache_manager import check_auto_expiry
    check_auto_expiry()

_check_expiry_once()

@contextmanager
def get_connection():
    global _db_initialized
    with _db_init_lock:
        if not _db_initialized:
            _db_initialized = True
            init_db()
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                url_hash TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        ''')


        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_config_ttl():
    try:
        days = int(addon.getSetting('cache_ttl_days') or '7')
        return days * 86400 if days > 0 else 0
    except Exception:
        return 7 * 86400

def clean_expired_cache(ttl_seconds):
    if ttl_seconds <= 0:
        return
    current_time = time.time()
    with get_connection() as conn:
        conn.cursor().execute(
            'DELETE FROM cache WHERE timestamp < ?', (current_time - ttl_seconds,)
        )

def save_to_cache(url, data):
    hash_val = hashlib.md5(url.encode()).hexdigest()
    with get_connection() as conn:
        conn.cursor().execute('''
            INSERT OR REPLACE INTO cache (url_hash, data, timestamp)
            VALUES (?, ?, ?)
        ''', (hash_val, json.dumps(data), time.time()))

def get_json(url, ttl=None):
    if ttl is None:
        ttl = get_config_ttl()

    try:
        cache_ttl_days = int(addon.getSetting('cache_ttl_days') or '7')
        cache_ttl_seconds = cache_ttl_days * 86400 if cache_ttl_days > 0 else 0

        if cache_ttl_days == 0:
            from resources.lib.cache_manager import clear_cache
            clear_cache()
        elif cache_ttl_days > 0:
            clean_expired_cache(cache_ttl_seconds)
    except Exception:
        pass

    hash_val = hashlib.md5(url.encode()).hexdigest()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT data, timestamp FROM cache WHERE url_hash = ?', (hash_val,))
        row = cursor.fetchone()
        if row:
            cached_data, timestamp = row[0], row[1]
            if time.time() - timestamp < ttl:
                return json.loads(cached_data)

    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=10)
        r.raise_for_status()
        data = r.json()
        save_to_cache(url, data)
        return data
    except Exception:
        return {}

def save_tvshow_season_episodes(tmdb_id, season, serie_name, original_name,
                                episodes_data, last_episode_num=None, imdb_id=None):
    if not episodes_data:
        return

    converted = [
        (ep[0], ep[1] if len(ep) > 1 else '', ep[3] if len(ep) > 3 else '',
         ep[4] if len(ep) > 4 else '', ep[2] if len(ep) > 2 else '')
        for ep in episodes_data
    ]

    get_kodi_service().save_tvshow_season_episodes(
        tmdb_id=str(tmdb_id), season=season, serie_name=serie_name,
        original_name=original_name, episodes_data=converted,
        imdb_id=imdb_id, last_episode_num=last_episode_num,
    )

def process_and_save_tvshow_season(tmdb_id, season_data, imdb_id=None, series_fanart=None):
    if not season_data or 'episodes' not in season_data:
        return False
    try:
        season_number = season_data.get('season_number', 0)
        serie_name = season_data.get('name', '')
        episodes_list = season_data.get('episodes', [])
        if not episodes_list:
            return False

        if series_fanart is None:
            try:
                show_src = open_season_api(tmdb_id)
                series_fanart = (
                    f"https://image.tmdb.org/t/p/original{show_src.get('backdrop_path')}"
                    if show_src.get('backdrop_path') else ''
                )
            except Exception:
                series_fanart = ''

        episodes_data = []
        for ep in episodes_list:
            thumbnail = ''
            if ep.get('still_path'):
                thumbnail = f"https://image.tmdb.org/t/p/w500{ep['still_path']}"
            episodes_data.append((
                ep.get('episode_number', 0),
                ep.get('name', ''),
                ep.get('overview', ''),
                thumbnail,
                series_fanart or thumbnail
            ))

        save_tvshow_season_episodes(
            tmdb_id=str(tmdb_id),
            season=season_number,
            serie_name=serie_name,
            original_name=serie_name,
            episodes_data=episodes_data,
            imdb_id=imdb_id
        )
        return True
    except Exception:
        return False

def search_movie_api(search, page=1):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={quote(search)}&page={page}&language={getString(30700)}'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def search_tvshow_api(search, page=1):
    url = f'https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={quote(search)}&page={page}&language={getString(30700)}'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def search_anime_api(search, page=1):
    url = f'https://api.jikan.moe/v4/anime?q={quote(search)}&page={page}'
    src = get_json(url)
    return src.get('pagination', {}).get('last_visible_page', 0), src.get('data', [])

def movies_popular_api(page=1):
    url = f'https://api.themoviedb.org/3/movie/popular?api_key={API_KEY}&page={page}&language={getString(30700)}'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def movies_api(page, t):
    url_map = {
        'premiere': f'https://api.themoviedb.org/3/movie/now_playing?api_key={API_KEY}&page={page}&language={getString(30700)}',
        'trending': f'https://api.themoviedb.org/3/trending/movie/day?api_key={API_KEY}&page={page}&language={getString(30700)}'
    }
    url = url_map.get(t)
    if not url:
        return 0, []
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def open_movie_api(id):
    url = f'https://api.themoviedb.org/3/movie/{id}?api_key={API_KEY}&append_to_response=external_ids&language={getString(30700)}'
    return get_json(url)

def tv_shows_popular_api(page=1):
    url = f'https://api.themoviedb.org/3/discover/tv?api_key={API_KEY}&page={page}&language={getString(30700)}&sort_by=popularity.desc&without_keywords=210024&include_adult=false&vote_average.lte=10&vote_count.gte=100'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def tv_shows_trending_api(page=1):
    url = f'https://api.themoviedb.org/3/discover/tv?api_key={API_KEY}&page={page}&language={getString(30700)}&sort_by=popularity.desc&without_keywords=210024,161919&include_adult=false'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def tv_shows_premiere_api(page=1):
    year = get_current_date()[:4]
    url = f'https://api.themoviedb.org/3/discover/tv?api_key={API_KEY}&sort_by=popularity.desc&first_air_date_year={year}&page={page}&language={getString(30700)}&without_keywords=210024'
    src = get_json(url)
    return src.get('total_pages', 0), src.get('results', [])

def open_season_api(id):
    url = f'https://api.themoviedb.org/3/tv/{id}?api_key={API_KEY}&append_to_response=external_ids&language={getString(30700)}'
    return get_json(url)

def _update_season_imdb_id(tmdb_id, season, imdb_id):
    get_kodi_service().update_tvshow_imdb_id(str(tmdb_id), season, imdb_id)

def show_episode_api(id, season, imdb_id=None):
    cache_key = f'{id}_{season}'

    with _season_cache_lock:
        if cache_key in _season_cache:
            cached = _season_cache[cache_key]
        else:
            cached = None

    if cached is not None:
        if imdb_id:
            try:
                _update_season_imdb_id(str(id), int(season), imdb_id)
            except Exception:
                pass
        return cached

    url = f'https://api.themoviedb.org/3/tv/{id}/season/{season}?api_key={API_KEY}&language={getString(30700)}'
    data = get_json(url)

    if data and 'episodes' in data:
        try:
            process_and_save_tvshow_season(id, data, imdb_id)
        except Exception:
            pass

    with _season_cache_lock:
        _season_cache[cache_key] = data
    return data

def find_tv_show_api(imdb):
    url = f'https://api.themoviedb.org/3/find/{imdb}?api_key={API_KEY}&external_source=imdb_id&language={getString(30700)}'
    return get_json(url)

def animes_popular_api(page=1):
    url = f'https://api.jikan.moe/v4/top/anime?page={page}&filter=bypopularity'
    src = get_json(url)
    return src.get('pagination', {}).get('last_visible_page', 0), src.get('data', [])

def animes_airing_api(page=1):
    url = f'https://api.jikan.moe/v4/seasons/now?page={page}'
    src = get_json(url)
    return src.get('pagination', {}).get('last_visible_page', 0), src.get('data', [])

def animes_by_season_api(year, season, page=1):
    url = f'https://api.jikan.moe/v4/seasons/{year}/{season}?page={page}'
    src = get_json(url)
    return src.get('pagination', {}).get('last_visible_page', 0), src.get('data', [])

def open_anime_api(id):
    url = f'https://api.jikan.moe/v4/anime/{id}/full'
    return get_json(url)

def open_anime_episodes_api(id):
    cache_url = f'https://cache.jikan.moe/anime/{id}/episodes_full'
    cached = get_json(cache_url)
    if cached and 'episodes' in cached:
        return cached['episodes']

    all_episodes = []
    page = 1
    first_request = True

    while True:
        url = f'https://api.jikan.moe/v4/anime/{id}/episodes?page={page}'
        src = get_json(url)
        episodes = src.get('data', [])
        if not episodes:
            break
        all_episodes.extend(episodes)
        if not src.get('pagination', {}).get('has_next_page', False):
            break
        page += 1
        if not first_request:
            time.sleep(0.4)
        first_request = False

    if not all_episodes:
        return all_episodes

    try:
        anime_info = open_anime_api(id).get('data', {})
        anime_name = anime_info.get('title', '')
        anime_name_english = anime_info.get('title_english', '')
        last_ep = max(ep.get('mal_id', 0) for ep in all_episodes)

        episodes_data = []
        for ep in all_episodes:
            episode_num = ep.get('mal_id', 0)
            title = ep.get('title', '')
            if ep.get('title_english'):
                title = ep.get('title_english')
            elif ep.get('title_romanji'):
                title = ep.get('title_romanji')
            episodes_data.append((
                episode_num, title, ep.get('url', ''), '', ep.get('synopsis', '') or '',
            ))

        save_to_cache(cache_url, {'episodes': all_episodes})
        get_kodi_service().save_anime_episodes(
            mal_id=str(id), anime_name=anime_name, original_name=anime_name_english,
            episodes_data=episodes_data, last_episode_num=last_ep,
        )
    except Exception:
        pass

    return all_episodes

def cleanhtml(raw_html):
    import re
    return re.sub(re.compile('<.*?>'), '', raw_html)

def get_date():
    src = get_json('http://worldtimeapi.org/api/timezone/America/New_York')
    datetime_str = src.get('datetime', '')
    if datetime_str:
        return datetime_str.split('-')[0], datetime_str.split('T')[0]
    from datetime import date
    today = date.today()
    return str(today.year), str(today)

