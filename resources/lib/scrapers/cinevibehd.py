# -*- coding: utf-8 -*-

WEBSITE = 'CINEVIBEHD'

import re
import difflib
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup

from resources.lib.resolver import Resolver

try:
    import xbmcaddon
    addon = xbmcaddon.Addon()
    DUBBED = addon.getLocalizedString(30200)
    SUBTITLED = addon.getLocalizedString(30202)
except:
    DUBBED = 'DUBLADO'
    SUBTITLED = 'LEGENDADO'

session = requests.Session()
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Referer': 'https://cinevibehd.com/',
})

class source:
    __site_url__ = ['https://cinevibehd.com/']

    @classmethod
    def normalize_title(cls, title):
        if not title:
            return ''
        title = re.sub(r'\s*[:]\s*', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        return title

    @classmethod
    def _fetch_nume_parallel(cls, post_id, nume_list, media_type):
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        req_headers = {
            'Referer': cls.__site_url__[-1],
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
        results = {}
        lock = threading.Lock()

        def _worker(nume):
            api = f"https://cinevibehd.com/wp-json/dooplayer/v2/{post_id}/{media_type}/{nume}"
            try:
                r = session.get(api, headers=req_headers, timeout=15)
                if not r or r.status_code != 200:
                    return

                embed = None
                try:
                    data = r.json()
                    embed = data.get('embed_url') or data.get('embed') or data.get('url') or data.get('player') or data.get('iframe')
                except:
                    pass

                if not embed:
                    m_if = re.search(r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]', r.text, re.I)
                    if m_if:
                        embed = m_if.group(1)

                if not embed:
                    m = re.search(r'(https?://[^\s\'"]+\.(?:m3u8|mp4)[^\s\'"]*)', r.text)
                    if m:
                        embed = m.group(1)

                if embed:
                    with lock:
                        results[nume] = embed
            except:
                pass

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(_worker, n) for n in nume_list]
            for f in as_completed(futures, timeout=20):
                try:
                    f.result()
                except Exception:
                    pass

        return results

    @classmethod
    def _get_player_urls(cls, post_id, html, season=None, episode=None):
        if not post_id:
            return []

        raw_nume = re.findall(r'data-nume=[\"\'](\d+)[\"\']', html or '')
        nume_list = list(set([n for n in raw_nume if n.lower() != 'trailer']))

        if not nume_list:
            return []

        media_type = 'movie' if (season is None or episode is None) else 'tv'
        embeds = cls._fetch_nume_parallel(post_id, nume_list, media_type)

        players = []
        dub_count = 0
        sub_count = 0
        for nume in nume_list:
            embed = embeds.get(nume)
            if not embed:
                continue

            title_match = re.search(rf'data-nume=[\"\']{nume}[\"\'][^>]*>.*?<span[^>]*class=["\']title["\'][^>]*>([^<]+)</span>', html or '', re.I | re.S)
            raw_title = title_match.group(1).strip() if title_match else ""
            is_dub = bool(re.search(r'dub|dublad|dublado', raw_title, re.I))
            lang = DUBBED if is_dub else SUBTITLED

            if is_dub:
                dub_count += 1
                number = dub_count
            else:
                sub_count += 1
                number = sub_count

            players.append((f"{WEBSITE} - {lang} {number}", embed))

        return players

    @classmethod
    def search_movies(cls, tmdb_id, year, movie_name, original_name):
        title_pt = cls.normalize_title(movie_name or '')
        if not title_pt:
            return []

        query = quote_plus(title_pt)
        search_url = f"https://cinevibehd.com/?s={query}"

        try:
            r = session.get(search_url, timeout=20)
            if r.status_code != 200:
                return []

            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.find_all('a', href=re.compile(r'/filmes/[^/]+/$'))

            best_url = None
            best_score = 0

            for a in items:
                href = a['href']
                text = a.get_text(strip=True)

                clean_text = re.sub(r'\(\d{4}\)', '', text).strip()
                text_year = re.search(r'\((\d{4})\)', text)
                text_year = text_year.group(1) if text_year else None

                ratio = difflib.SequenceMatcher(None, title_pt.lower(), clean_text.lower()).ratio()
                score = ratio

                if year and text_year and abs(int(year) - int(text_year)) <= 1:
                    score += 0.4

                if score > best_score and score > 0.78:
                    best_score = score
                    best_url = href

            if not best_url:
                return []

            film_resp = session.get(best_url, timeout=20)
            if film_resp.status_code != 200:
                return []

            post_id_match = re.search(r'data-post=["\'](\d+)["\']', film_resp.text)
            if not post_id_match:
                return []

            post_id = post_id_match.group(1)
            return cls._get_player_urls(post_id, film_resp.text)

        except Exception:
            return []

    @classmethod
    def search_tvshows(cls, tmdb_id, season, episode, serie_name, original_name):
        title_pt = cls.normalize_title(serie_name or '')
        if not title_pt:
            return []

        s = str(int(season))
        e = str(int(episode)).zfill(2)

        try:
            search_url = f"https://cinevibehd.com/?s={quote_plus(title_pt)}"
            r = session.get(search_url, timeout=20)
            if r.status_code != 200:
                return []

            soup = BeautifulSoup(r.text, 'html.parser')
            best_score = 0
            serie_link = None
            for a in soup.find_all('a', href=re.compile(r'/series/[^/]+/$')):
                text = a.get_text(strip=True)
                clean_text = re.sub(r'\(\d{4}\)', '', text).strip()
                ratio = difflib.SequenceMatcher(None, title_pt.lower(), clean_text.lower()).ratio()
                if ratio >= 0.5 and ratio > best_score:
                    best_score = ratio
                    serie_link = a
            if not serie_link:
                return []

            series_url = serie_link['href']
            series_resp = session.get(series_url, timeout=30)
            if series_resp.status_code != 200:
                return []

            html = series_resp.text
            soup_series = BeautifulSoup(html, 'html.parser')

            episode_pattern = re.compile(rf'/episodios/[^/]+-{s}x{e}[^/]*/?$', re.I)
            ep_link = soup_series.find('a', href=episode_pattern)

            if not ep_link:
                fallback_patterns = [
                    rf'{s}x{int(episode)}',
                    rf'{s}x{int(episode):02d}',
                    rf'{int(s):02d}x{int(episode):02d}',
                ]
                for pat in fallback_patterns:
                    ep_link = soup_series.find('a', href=re.compile(rf'/episodios/[^/]+-{pat}[^/]*/?$', re.I))
                    if ep_link:
                        break

            if not ep_link:
                return []

            episode_url = ep_link['href']
            if not episode_url.startswith('http'):
                episode_url = 'https://cinevibehd.com' + episode_url

            ep_resp = session.get(episode_url, timeout=30)
            if ep_resp.status_code != 200:
                return []

            post_id_match = re.search(r'data-post=["\'](\d+)["\']', ep_resp.text)
            if not post_id_match:
                return []

            post_id = post_id_match.group(1)
            return cls._get_player_urls(post_id, ep_resp.text, season=season, episode=episode)

        except Exception:
            return []

    @classmethod
    def resolve_movies(cls, url):
        streams = []
        if not url:
            return streams

        sub = ''
        try:
            if 'http' in url:
                parts = url.split('http')
                sub_candidate = 'http' + parts[-1].split('&')[0]
                if '.srt' in sub_candidate:
                    sub = sub_candidate
        except:
            pass

        stream = url.split('?')[0].split('#')[0]
        resolver = Resolver()
        resolved, sub_from_resolver = resolver.resolverurls(stream)
        if resolved:
            streams.append((resolved, sub or sub_from_resolver, USER_AGENT))

        return streams

    @classmethod
    def resolve_tvshows(cls, url):
        return cls.resolve_movies(url)
