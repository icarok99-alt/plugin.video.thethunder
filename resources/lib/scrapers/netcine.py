# -*- coding: utf-8 -*-

WEBSITE = 'NETCINE'

import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin
import re
import difflib
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from resources.lib.resolver import Resolver

try:
    import xbmcaddon
    addon = xbmcaddon.Addon()
    DUBBED = addon.getLocalizedString(30200)
    SUBTITLED = addon.getLocalizedString(30202)
except:
    DUBBED = 'DUBLADO'
    SUBTITLED = 'LEGENDADO'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
ORIGINAL_BASE = 'https://netcinett.lat'

session = requests.Session()
session.verify = False
session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Referer': ORIGINAL_BASE + '/',
})

_host_cache = None


def _get_host():
    global _host_cache
    if _host_cache:
        return _host_cache
    try:
        r = session.get(ORIGINAL_BASE, allow_redirects=True, timeout=10)
        final = r.url.rstrip('/')
        if 'netcine' in final.lower():
            _host_cache = final + '/'
            return _host_cache
    except:
        pass
    _host_cache = ORIGINAL_BASE + '/'
    return _host_cache


def _clean_title(title):
    return re.sub(r'[:\-\u2014]', ' ', title).strip()


class source:
    __site_url__ = [ORIGINAL_BASE + '/']

    @classmethod
    def search_movies(cls, tmdb_id, year, movie_name, original_name):
        host = _get_host()
        title_pt = movie_name or ''
        original_title = original_name or title_pt
        tmdb_year = str(year) if year else ''
        if not title_pt and not original_title:
            return []
        search_titles = [(title_pt, True)]
        if original_title and original_title != title_pt:
            search_titles.append((original_title, False))
        for search_title, _ in search_titles:
            try:
                r = session.get(host + '?s=' + quote_plus(_clean_title(search_title)), timeout=15)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, 'html.parser')
                best_score = 0
                best_href = None
                for item in soup.select('#box_movies .movie'):
                    a = item.select_one('.imagen a')
                    if not a:
                        continue
                    href = urljoin(host, a['href'])
                    if '/tvshows/' in href:
                        continue
                    page_title = item.select_one('h2').get_text(strip=True)
                    year_span = item.select_one('span.year')
                    page_year_raw = year_span.get_text(strip=True) if year_span else ''
                    m = re.search(r'\d{4}', page_year_raw)
                    page_year = m.group(0) if m else ''
                    if tmdb_year and page_year and page_year != tmdb_year:
                        continue
                    clean_page = re.sub(r'(?i)\s*(dublado|legendado|hd|4k|1080p|720p|cam|ts).*', '', page_title).strip()
                    ratio = difflib.SequenceMatcher(None, search_title.lower(), clean_page.lower()).ratio()
                    if ratio >= 0.5 and ratio > best_score:
                        best_score = ratio
                        best_href = href
                if best_href:
                    return cls._get_players(best_href)
            except:
                pass
        return []

    @classmethod
    def search_tvshows(cls, tmdb_id, season, episode, serie_name, original_name):
        host = _get_host()
        title_pt = serie_name or ''
        original_title = original_name or title_pt
        if not title_pt and not original_title:
            return []
        search_titles = [(title_pt, True)]
        if original_title and original_title != title_pt:
            search_titles.append((original_title, False))
        for search_title, _ in search_titles:
            try:
                r = session.get(host + '?s=' + quote_plus(_clean_title(search_title)), timeout=15)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, 'html.parser')
                best_score = 0
                series_href = None
                for item in soup.select('#box_movies .movie'):
                    a = item.select_one('.imagen a')
                    if not a or '/tvshows/' not in a['href']:
                        continue
                    href = urljoin(host, a['href'])
                    page_title = item.select_one('h2').get_text(strip=True)
                    clean_page = re.sub(r'(?i)\s*(dublado|legendado|hd|4k|1080p|720p|cam|ts).*', '', page_title).strip()
                    ratio = difflib.SequenceMatcher(None, search_title.lower(), clean_page.lower()).ratio()
                    if ratio >= 0.5 and ratio > best_score:
                        best_score = ratio
                        series_href = href
                if not series_href:
                    continue
                r2 = session.get(series_href, timeout=15)
                soup2 = BeautifulSoup(r2.text, 'html.parser')
                season_int = int(season)
                episode_int = int(episode)
                patterns = [
                    '%d - %d' % (season_int, episode_int),
                    '%d - %02d' % (season_int, episode_int),
                    '%dx%02d' % (season_int, episode_int),
                    '%dx%d' % (season_int, episode_int),
                ]
                for link in soup2.select('a[href*="/episode/"]'):
                    text = link.get_text(strip=True)
                    for pat in patterns:
                        if pat in text:
                            return cls._get_players(urljoin(host, link['href']))
            except:
                pass
        return []

    @classmethod
    def _get_players(cls, page_url):
        links = []
        try:
            host = _get_host()
            r = session.get(page_url, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            for tab in soup.select('#player-container .player-menu li a'):
                text = tab.get_text(strip=True).upper()
                tab_id = tab['href'].lstrip('#')
                iframe = soup.select_one('#' + tab_id + ' iframe')
                if iframe and iframe.get('src'):
                    src = iframe['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif not src.startswith('http'):
                        src = urljoin(host, src)
                    lang = DUBBED if any(x in text for x in ['DUBLAD', 'DUB', 'AUDIO']) else SUBTITLED
                    links.append(('%s - %s' % (WEBSITE, lang), src))
        except:
            pass
        return links

    @classmethod
    def resolve_movies(cls, url):
        streams = []
        if not url:
            return streams
        try:
            resolved, sub = Resolver().resolverurls(url)
            if resolved:
                streams.append((resolved, sub or '', USER_AGENT))
        except:
            pass
        return streams

    @classmethod
    def resolve_tvshows(cls, url):
        return cls.resolve_movies(url)
