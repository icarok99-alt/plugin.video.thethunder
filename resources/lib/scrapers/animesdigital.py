# -*- coding: utf-8 -*-

WEBSITE = 'ANIMESDIGITAL'

import re
import unicodedata
import difflib
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import requests

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
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://animesdigital.org/',
})

LINK_SELECTORS = [
    'div.itemA > a[href*="/anime/a/"]',
    'div.itemA > a[href*="/filme/"]',
    'div.itemA a[href*="/anime/"]',
    'div.itemA a[href*="/filme/"]',
    'article a[href*="/anime/"]',
    'article a[href*="/filme/"]',
    'a[href*="animesdigital.org/anime/"]',
    'a[href*="animesdigital.org/filme/"]',
    'div.item a[href*="/anime/"]',
    'div.item a[href*="/filme/"]',
]

VIDEO_SELECTORS = [
    'div.item_ep a.b_flex[href*="/video/a/"]',
    'div.item_ep a.b_flex[href*="/video/"]',
    'div.item_ep a[href*="/video/"]',
    'a.b_flex[href*="/video/"]',
    'a[href*="/video/"]',
]


class source:

    QUOTE_MIN_CHARS = 60
    QUOTE_MIN_WORDS = 8

    @classmethod
    def _normalize(cls, text):
        return unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode('ascii')

    @classmethod
    def _adjust_base_title(cls, title):
        if not title or '"' not in title:
            return title
        words = title.split()
        if len(title) < cls.QUOTE_MIN_CHARS and len(words) < cls.QUOTE_MIN_WORDS:
            return title
        return title.split('"', 1)[0].strip()

    @classmethod
    def _clean_title(cls, title):
        t = cls._normalize(title.lower())
        t = re.sub(r'^(?:assistir|ver)\s+(?:online\s+)?', '', t, flags=re.I)
        t = re.sub(r'^(?:assistir|ver)\b\s*', '', t, flags=re.I)
        t = re.sub(
            r'\s+(?:em\s*hd|hd|fhd|fullhd|1080p|720p|completo|dublado|legendado'
            r'|dub|sub|pt-?br|todos\s+os?\s+epis\xf3dios?|episodios|todos).*$',
            '', t, flags=re.I
        )
        t = re.sub(
            r'\s+online\s+(?:hd|fhd|fullhd|1080p|720p|completo|dublado|legendado|dub|sub).*$',
            '', t, flags=re.I
        )
        t = re.sub(r'\b(?:anime|todos|os|ep\.?|episodios?|assistir|ver|em|hd|fhd|full|todos)\b\s*', '', t, flags=re.I)
        t = re.sub(r'(\s*(?:season|temporada|part|cour|s)\s*\d+).*$', r'\1', t, flags=re.I)
        t = re.sub(r'\b(?:season|temporada|part|cour|s)\b\s*(\d+)', r'\1', t, flags=re.I)
        t = re.sub(r'[-\u2014\u2013:.,;!?]+', ' ', t)
        t = re.sub(r'[()[\]{}"\'`\xb4]', '', t)
        return re.sub(r'\s+', ' ', t).strip()

    @classmethod
    def _strip_dublado(cls, text):
        return re.sub(r'\bdublado\b', '', text, flags=re.I).strip()

    @classmethod
    def _extract_year(cls, text):
        m = re.search(r'\b(19|20)\d{2}\b', text or '')
        return int(m.group()) if m else None

    @classmethod
    def _extract_season_from_title(cls, title):
        if not title:
            return None
        for pattern in [
            r'\b(?:season|temporada|part|cour)\s*(\d+)\b',
            r'\b(\d+)(?:nd|rd|th|st)\s*(?:season|temporada)\b',
            r':\s*(?:season|temporada)\s*(\d+)\b',
            r'\bs(\d+)\b',
        ]:
            m = re.search(pattern, title, re.I)
            if m:
                try:
                    n = int(m.group(1))
                    if 1 <= n <= 20:
                        return n
                except:
                    pass
        return None

    @classmethod
    def _similarity_score(cls, base_titles, candidate_title, base_year=None, cand_year=None, season=None, is_movie=False):
        try:
            season_num = int(season) if season is not None else None
        except:
            season_num = None

        cand_clean = cls._clean_title(candidate_title)
        stripped_cand = cls._strip_dublado(cand_clean)
        cand_lower = candidate_title.lower()
        best_score = 0.0
        roman_match = re.search(r'\b(i{1,3}|iv|v|vi{0,3}|ix|x{1,3})\b', cand_lower, re.I)

        for base in base_titles:
            base = cls._adjust_base_title(base)
            base_clean = cls._clean_title(base)
            base_lower = base.lower()
            base_no_movie = re.sub(r'\bmovie\b', '', base_clean, flags=re.I).strip()
            cand_no_movie = re.sub(r'\bmovie\b', '', cand_clean, flags=re.I).strip()
            stripped_no_movie = re.sub(r'\bmovie\b', '', stripped_cand, flags=re.I).strip()

            if season_num and season_num > 1 and not is_movie:
                base_super = re.split(r'(?:season|second|part|temporada|:\s*|\u2013\s*).*$', base.lower(), flags=re.I)[0].strip()
                base_super_clean = cls._clean_title(base_super)
                norm_base = re.sub(r'\bmovie\b', '', base_super_clean, flags=re.I).strip()
            else:
                norm_base = base_no_movie

            norm_cand = stripped_no_movie

            if season_num and season_num > 1 and not is_movie:
                season_str = str(season_num)
                roman_str = roman_match.group(0).lower() if roman_match else ''
                if not (season_str in norm_cand or roman_str in norm_cand):
                    continue
                if not any(norm_cand.startswith(norm_base + ' ' + x) or norm_cand == norm_base + ' ' + x
                           for x in [season_str, roman_str]):
                    continue
            else:
                if norm_cand != norm_base:
                    if difflib.SequenceMatcher(None, norm_base, norm_cand).ratio() < 0.85:
                        continue

            score = max(
                difflib.SequenceMatcher(None, base_no_movie, stripped_no_movie).ratio(),
                difflib.SequenceMatcher(None, base_lower, cand_lower).ratio(),
            )
            if 'dublado' in cand_lower:
                score += 0.25
            if season_num and (str(season_num) in candidate_title or roman_match):
                score += 0.20
            if base_year and cand_year:
                score += 0.40 if base_year == cand_year else -0.55
            best_score = max(best_score, score)

        return best_score

    @classmethod
    def _build_search_title(cls, title, season):
        try:
            season_num = int(season) if season is not None else None
        except:
            season_num = None

        base = re.sub(r'\s*(?:season|part|temporada|cour)\s*\d+.*$', '', title, flags=re.I)
        base = re.sub(r'\s*\d+(?:nd|rd|th)?\s*season.*$', '', base, flags=re.I)
        base = re.sub(r'\s*:\s*.*$', '', base)
        base = re.sub(r'\s*\d{4}$', '', base).strip()

        if season_num and season_num > 1:
            base = '%s %d' % (base, season_num)

        return re.sub(r'\s+', ' ', re.sub(r'[-\u2014\u2013:]+', ' ', base)).strip()

    @classmethod
    def search_animes(cls, mal_id, episode, anime_name, original_name, year=None):
        is_movie = episode is None
        if not is_movie:
            try:
                episode = int(episode)
            except:
                return []

        base_titles_raw = [t for t in [anime_name, original_name] if t]
        if not base_titles_raw:
            return []
        base_titles = [cls._adjust_base_title(t) for t in base_titles_raw]

        season = (
            cls._extract_season_from_title(base_titles[0])
            or (cls._extract_season_from_title(base_titles[1]) if len(base_titles) > 1 else None)
        )
        search_title = cls._build_search_title(base_titles[0], season)

        r = session.get('https://animesdigital.org/?s=' + quote_plus(search_title))
        if not r.ok:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        anchors = []
        for sel in LINK_SELECTORS:
            anchors = soup.select(sel)
            if anchors:
                break

        if not anchors and len(base_titles) > 1 and base_titles[1] != base_titles[0]:
            fallback = cls._build_search_title(base_titles[1], season)
            if fallback != search_title:
                r = session.get('https://animesdigital.org/?s=' + quote_plus(fallback))
                if r.ok:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    for sel in LINK_SELECTORS:
                        anchors = soup.select(sel)
                        if anchors:
                            break

        if not anchors:
            return []

        candidates = []
        for a in anchors:
            title = a.get('title') or a.get_text(strip=True)
            url = a['href']
            cand_year = cls._extract_year(title)
            score = cls._similarity_score(base_titles, title, year, cand_year, season, is_movie)
            candidates.append({'title': title, 'url': url, 'score': score})

        candidates.sort(key=lambda x: x['score'], reverse=True)

        results = []
        seen = set()

        for c in candidates[:10]:
            if c['score'] < 0.70 or c['url'] in seen:
                continue
            seen.add(c['url'])

            if is_movie and '/filme/' in c['url']:
                ep_url = c['url']
            elif is_movie:
                ep_url = cls._get_movie_video_url(c['url'])
            else:
                ep_url = cls._get_episode_page_url(c['url'], episode)

            if not ep_url:
                continue
            r_ep = session.get(ep_url)
            if not r_ep.ok:
                continue
            players = cls._get_all_players(r_ep.text)
            if not players:
                continue
            prefix = DUBBED if 'dublado' in c['title'].lower() else SUBTITLED
            for i, (q, u) in enumerate(players, 1):
                results.append(('ANIMESDIGITAL - %s %d' % (prefix, i), u))

        return results

    @classmethod
    def _get_movie_video_url(cls, url):
        try:
            r = session.get(url)
            if not r.ok:
                return None
            soup = BeautifulSoup(r.text, 'html.parser')
            for sel in VIDEO_SELECTORS:
                link = soup.select_one(sel)
                if link and link.get('href'):
                    return link['href']
        except:
            pass
        return None

    @classmethod
    def _get_episode_page_url(cls, anime_url, episode):
        base = anime_url.split('?')[0].rstrip('/')
        page = 1
        while True:
            url = (base + '?odr=1') if page == 1 else (base + '/page/%d/?odr=1' % page)
            r = session.get(url)
            if not r.ok:
                break
            soup = BeautifulSoup(r.text, 'html.parser')
            for item in soup.select('div.item_ep'):
                a = item.select_one('a.b_flex[href*="/video/"]')
                t = item.select_one('div.title_anime')
                if a and t:
                    m = re.search(r'Epis\xf3dio\s*(\d+)', t.get_text(strip=True), re.I)
                    if m and int(m.group(1)) == episode:
                        return a['href']
            page += 1
        return None

    @classmethod
    def _get_all_players(cls, text):
        soup = BeautifulSoup(text, 'html.parser')
        players = []

        for li in soup.select('li[data-tab]'):
            tab = li.get('data-tab')
            if tab:
                iframe = soup.select_one(tab + ' iframe[src]')
                if iframe:
                    label = li.get_text(strip=True).upper()
                    q = 'FULLHD' if ('FHD' in label or 'FULL' in label) else 'HD'
                    players.append((q, iframe['src']))

        if players:
            return players

        for div in soup.find_all('div', id=re.compile(r'^player\d+')):
            iframe = div.find('iframe', src=True)
            if iframe:
                q = 'FULLHD' if ('fhd' in div.get('id', '').lower() or 'full' in div.get('id', '').lower()) else 'HD'
                players.append((q, iframe['src']))

        if players:
            return players

        for iframe in soup.find_all('iframe', src=True):
            src = iframe['src'].lower()
            if any(k in src for k in ['video', 'player', 'stream', '.m3u8', '.mp4']):
                players.append(('HD', iframe['src']))

        return players

    @classmethod
    def resolve_animes(cls, url):
        resolved, sub = Resolver().resolverurls(url)
        return [(resolved or url, sub or '', USER_AGENT)]

    resolve_animes_movies = resolve_animes
    __site_url__ = ['https://animesdigital.org/']
