# -*- coding: utf-8 -*-

import os
import re
import sys
import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import xbmcplugin
import threading
from datetime import datetime
import json
from resources.lib.helper import *
from resources.lib import httpclient, sources
from resources.lib.kodi_service import get_service as get_kodi_service, WINDOW_PROP
from urllib.parse import urlparse, unquote, parse_qs

_addon = xbmcaddon.Addon()

def getString(string_id):
    return _addon.getLocalizedString(string_id)

from resources.lib.windows.loading_manager import loading_manager

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

try:
    from resources.lib import update
    update.auto_update()
except:
    pass

class Donate(xbmcgui.WindowDialog):
    def __init__(self):
        super().__init__()
        addon = xbmcaddon.Addon()
        home_dir = addon.getAddonInfo('path')
        translate = xbmcvfs.translatePath
        pix_image = translate(os.path.join(home_dir, 'resources', 'images', 'qrcode-pix.png'))
        self.image = xbmcgui.ControlImage(440, 145, 400, 400, pix_image)
        self.text = xbmcgui.ControlLabel(
            x=455, y=570, width=1280, height=25,
            label=getString(30500),
            textColor='white'
        )
        self.text2 = xbmcgui.ControlLabel(
            x=535, y=600, width=1280, height=25,
            label=getString(30501),
            textColor='white'
        )
        self.addControl(self.image)
        self.addControl(self.text)
        self.addControl(self.text2)

def get_icon(image_name):
    addon = xbmcaddon.Addon()
    home_dir = addon.getAddonInfo('path')
    translate = xbmcvfs.translatePath
    return translate(os.path.join(home_dir, 'resources', 'images', f'{image_name}.png'))

def stop_player():
    try:
        player = xbmc.Player()
        if player.isPlaying():
            player.stop()
            xbmc.sleep(300)
    except:
        pass

def get_preferred_language():
    try:
        addon = xbmcaddon.Addon()
        valor = addon.getSetting("preferred_language")
        if valor == "0":
            return getString(30200)
        else:
            return getString(30202)
    except:
        return getString(30200)

def is_auto_play_enabled():
    try:
        return xbmcaddon.Addon().getSetting("auto_play_enabled") == "true"
    except:
        return False

def build_tvshow_playlist(tmdb_id, season_num, current_episode_num, serie_name, original_name, all_episodes, imdb_id):
    if not all_episodes or not isinstance(all_episodes, list):
        return

    if not isinstance(season_num, int) or not isinstance(current_episode_num, int):
        return

    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()

    for episode_data in all_episodes:
        if not isinstance(episode_data, dict):
            continue

        ep_num = episode_data.get('episode')
        if not ep_num or not isinstance(ep_num, int):
            continue

        name = episode_data.get('episode_title', '')
        img = episode_data.get('thumbnail', '')
        fanart = episode_data.get('fanart', '')
        description = episode_data.get('description', '')

        if ep_num >= current_episode_num:
            params = {
                'serie_name': serie_name,
                'original_name': original_name,
                'tmdb_id': str(tmdb_id),
                'imdb': imdb_id,
                'season_num': str(season_num),
                'episode_num': str(ep_num),
                'episode_title': name,
                'iconimage': img,
                'fanart': fanart,
                'description': description
            }

            plugin_url = 'plugin://plugin.video.thethunder/play_resolve_tvshows/{}'.format(urlencode(params))

            title = name if name else '{}x{}'.format(season_num, str(ep_num).zfill(2))

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': img, 'icon': img, 'fanart': fanart or img})

            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(name if name else title)
            info_tag.setTvShowTitle(serie_name)
            info_tag.setPlot(description)
            info_tag.setMediaType('episode')
            info_tag.setSeason(season_num)
            info_tag.setEpisode(ep_num)
            if original_name:
                info_tag.setOriginalTitle(original_name)

            playlist.add(url=plugin_url, listitem=list_item)

def build_anime_playlist(mal_id, current_episode_num, anime_name, original_name, all_episodes):
    if not all_episodes or not isinstance(all_episodes, list):
        return

    if not isinstance(current_episode_num, int):
        return

    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()

    for episode_data in all_episodes:
        if not isinstance(episode_data, dict):
            continue

        ep_num = episode_data.get('episode')
        if not ep_num or not isinstance(ep_num, int):
            continue

        name = episode_data.get('episode_title', '')
        img = episode_data.get('thumbnail', '')
        fanart = episode_data.get('fanart', '')
        description = episode_data.get('description', '')

        if ep_num >= current_episode_num:
            params = {
                'anime_name': anime_name,
                'original_name': original_name,
                'mal_id': str(mal_id),
                'episode_num': str(ep_num),
                'episode_title': name,
                'iconimage': img,
                'fanart': fanart,
                'description': description
            }

            plugin_url = 'plugin://plugin.video.thethunder/play_resolve_animes/{}'.format(urlencode(params))

            title = 'Ep {} {}'.format(ep_num, name) if name else 'Ep {}'.format(ep_num)

            list_item = xbmcgui.ListItem(title)
            list_item.setArt({'thumb': img, 'icon': img, 'fanart': fanart or img})

            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(name if name else f'Ep {ep_num}')
            info_tag.setTvShowTitle(anime_name)
            info_tag.setPlot(description)
            info_tag.setMediaType('episode')
            info_tag.setSeason(1)
            info_tag.setEpisode(ep_num)
            if original_name:
                info_tag.setOriginalTitle(original_name)

            playlist.add(url=plugin_url, listitem=list_item)

def try_resolve_with_fallback(menus_links, resolver):
    if not menus_links:
        return None, None
    preferred_lang = get_preferred_language().upper()
    TOP_HOSTS = ["DOODSTREAM", "STREAMTAPE", "NETCINE", "MIXDROP", "FILEMOON"]

    def get_priority_score(label, url=""):
        label_u = (label or "").upper()
        score = 0
        if "DUBBED" in preferred_lang or "DUBLADO" in preferred_lang:
            if any(x in label_u for x in ["DUBLADO", "DUB", "DUBBED", "PT-BR", "PORTUGUÊS", "PTBR"]):
                score += 1000
        else:
            if any(x in label_u for x in ["LEGENDADO", "LEG", "SUB", "SUBTITLED"]):
                score += 1000
        url_lower = url.lower() if url else ""
        for i, host in enumerate(TOP_HOSTS):
            if host in label_u or host.lower() in url_lower:
                score += (len(TOP_HOSTS) - i) * 10
                break
        return score

    sorted_links = sorted(menus_links, key=lambda x: get_priority_score(x[0], x[1]), reverse=True)
    tried = set()
    for name, url in sorted_links:
        try:
            decoded = unquote(url)
            parsed = urlparse(decoded)
            qs = parse_qs(parsed.query)
            final_url = qs.get('url', [decoded])[0] or qs.get('u', [decoded])[0] or decoded
            if final_url in tried:
                continue
            tried.add(final_url)

            stream, sub = resolver(final_url)

            if stream:
                return stream, sub
        except:
            continue
    return None, None

def auto_play_preferred_language(mal_id, tmdb_id, imdb, year, season, episode, video_title, iconimage, fanart, description, is_anime='false', movie_name='', serie_name='', original_name='', anime_name=''):
    try:
        if is_anime == 'true':
            if episode is None:
                menus_links = sources.movie_content_anime(mal_id, anime_name, original_name)
                resolver = lambda url: sources.resolve_anime_movies(url)
            else:
                menus_links = sources.show_content_anime(mal_id, episode, anime_name, original_name)
                resolver = lambda url: sources.resolve_animes(url)
        elif season is None and episode is None:
            menus_links = sources.movie_content(tmdb_id, year, movie_name, original_name)
            resolver = lambda url: sources.resolve_movies(url)
        else:
            menus_links = sources.show_content(tmdb_id, season, episode, serie_name, original_name)
            resolver = lambda url: sources.resolve_tvshows(url)

        if not menus_links:
            notify(getString(30401))
            return False

        stream, sub = try_resolve_with_fallback(menus_links, resolver)

        if not stream:
            notify(getString(30402))
            return False
        stop_player()

        play_item = xbmcgui.ListItem(path=stream)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart})

        if season and episode:
            showtitle = serie_name
            episode_title = video_title or f"{getString(30602)} {episode}"

            info_tag = play_item.getVideoInfoTag()
            info_tag.setTitle(episode_title)
            info_tag.setTvShowTitle(showtitle)
            info_tag.setPlot(description)
            info_tag.setMediaType('episode')
            if tmdb_id:
                info_tag.setUniqueIDs({'tmdb': tmdb_id}, 'tmdb')
        else:
            info_tag = play_item.getVideoInfoTag()
            info_tag.setTitle(video_title)
            info_tag.setPlot(description)
            info_tag.setMediaType('movie')
            if year:
                info_tag.setYear(int(year))

        if sub:
            play_item.setSubtitles([sub])
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
        return True
    except:
        return False

@route('/')
def index():
    addMenuItem({'name': getString(30000), 'description': '', 'iconimage': get_icon('movies')}, destiny='/movies')
    addMenuItem({'name': getString(30001), 'description': '', 'iconimage': get_icon('tvshows')}, destiny='/tvshows')
    addMenuItem({'name': getString(30002), 'description': '', 'iconimage': get_icon('animes')}, destiny='/anime')
    addMenuItem({'name': getString(30018), 'description': '', 'iconimage': get_icon('donate')}, destiny='/donate', folder=False)
    addMenuItem({'name': getString(30017), 'description': '', 'iconimage': get_icon('settings')}, destiny='/settings', folder=False)
    end()
    setview('WideList')

@route('/donate')
def donate():
    try:
        donate_window = Donate()
        donate_window.doModal()
        del donate_window
    except:
        pass

@route('/settings')
def settings():
    addon = xbmcaddon.Addon()
    addon.openSettings()

@route('/movies')
def movies():
    addMenuItem({'name': getString(30003), 'description': '', 'iconimage': get_icon('premiere')}, destiny='/premiere_movies')
    addMenuItem({'name': getString(30005), 'description': '', 'iconimage': get_icon('trending')}, destiny='/trending_movies')
    addMenuItem({'name': getString(30007), 'description': '', 'iconimage': get_icon('popular')}, destiny='/popular_movies')
    addMenuItem({'name': getString(30014), 'description': '', 'iconimage': get_icon('search')}, destiny='/search_movies')
    end()
    setview('WideList')

@route('/tvshows')
def tvshows():
    addMenuItem({'name': getString(30004), 'description': '', 'iconimage': get_icon('premiere')}, destiny='/premiere_tvshows')
    addMenuItem({'name': getString(30006), 'description': '', 'iconimage': get_icon('trending')}, destiny='/trending_tvshows')
    addMenuItem({'name': getString(30008), 'description': '', 'iconimage': get_icon('popular')}, destiny='/popular_tvshows')
    addMenuItem({'name': getString(30015), 'description': '', 'iconimage': get_icon('search')}, destiny='/search_tvshows')
    end()
    setview('WideList')

@route('/anime')
def anime():
    addMenuItem({'name': getString(30009), 'description': '', 'iconimage': get_icon('popular')}, destiny='/popular_anime')
    addMenuItem({'name': getString(30010), 'description': '', 'iconimage': get_icon('airing')}, destiny='/airing_anime')
    addMenuItem({'name': getString(30011), 'description': '', 'iconimage': get_icon('premiere')}, destiny='/animes_by_year')
    addMenuItem({'name': getString(30016), 'description': '', 'iconimage': get_icon('search')}, destiny='/search_anime')
    end()
    setview('WideList')

@route('/search_movies')
def search_movies(param=None):
    param = param or {}
    search = param.get('search') if 'search' in param else input_text(heading=getString(30014))
    if not search:
        return
    page = int(param.get('page', 1))
    total_pages, results = httpclient.search_movie_api(search, page)
    setcontent('movies')
    for movie in results:
        title = movie.get('title') or movie.get('name')
        year = movie.get('release_date', '')[:4] or movie.get('first_air_date', '')[:4]
        display_name = f"{title} ({year})" if year else title
        icon = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else get_icon('movies')
        fanart = f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else ''
        description = movie.get('overview', '')
        original_name = movie.get('original_title', '')

        addMenuItem({
            'name': display_name,
            'tmdb_id': str(movie['id']),
            'year': year,
            'iconimage': icon,
            'fanart': fanart,
            'description': description,
            'movie_name': title,
            'original_name': original_name,
            'playable': 'true'
        }, destiny='/play_resolve_movies', folder=False)
    if page < total_pages:
        addMenuItem({
            'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
            'iconimage': get_icon('next'),
            'search': search,
            'page': str(page + 1)
        }, destiny='/search_movies')
    end()
    setview('List')

@route('/search_tvshows')
def search_tvshows(param=None):
    param = param or {}
    search = param.get('search') if 'search' in param else input_text(heading=getString(30015))
    if not search:
        return
    page = int(param.get('page', 1))
    total_pages, results = httpclient.search_tvshow_api(search, page)
    setcontent('tvshows')
    for show in results:
        title = show.get('title') or show.get('name')
        year = show.get('release_date', '')[:4] or show.get('first_air_date', '')[:4]
        display_name = f"{title} ({year})" if year else title
        icon = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else get_icon('tvshows')
        fanart = f"https://image.tmdb.org/t/p/original{show.get('backdrop_path')}" if show.get('backdrop_path') else ''
        description = show.get('overview', '')
        original_name = show.get('original_name', '')
        addMenuItem({
            'name': display_name,
            'tmdb_id': str(show['id']),
            'iconimage': icon,
            'fanart': fanart,
            'description': description,
            'serie_name': title,
            'original_name': original_name
        }, destiny='/tvshow_season')
    if page < total_pages:
        addMenuItem({
            'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
            'iconimage': get_icon('next'),
            'search': search,
            'page': str(page + 1)
        }, destiny='/search_tvshows')
    end()
    setview('List')

@route('/search_anime')
def search_anime(param=None):
    param = param or {}
    search = param.get('search') if 'search' in param else input_text(heading=getString(30016))
    if not search:
        return
    page = int(param.get('page', 1))
    total_pages, results = httpclient.search_anime_api(search, page)
    setcontent('tvshows')
    for anime in results:
        title = anime.get('title_english') or anime.get('title')
        original_name = anime.get('title', '')
        year = str(anime.get('year') or '')
        display_name = f"{title} ({year})" if year else title
        icon = anime.get('images', {}).get('jpg', {}).get('large_image_url') or get_icon('animes')
        fanart = icon
        description = anime.get('synopsis', '')
        addMenuItem({
            'name': display_name,
            'mal_id': str(anime['mal_id']),
            'iconimage': icon,
            'fanart': fanart,
            'description': description,
            'anime_name': title,
            'original_name': original_name
        }, destiny='/anime_episodes')
    if page < total_pages:
        addMenuItem({
            'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
            'iconimage': get_icon('next'),
            'search': search,
            'page': str(page + 1)
        }, destiny='/search_anime')
    end()
    setview('List')

@route('/popular_movies')
def popular_movies(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.movies_popular_api(page)
    if results:
        setcontent('movies')
        for movie in results:
            title = movie.get('title') or movie.get('name')
            year = movie.get('release_date', '')[:4] or movie.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else get_icon('movies')
            fanart = f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else ''
            description = movie.get('overview', '')
            original_name = movie.get('original_title', '')
            tmdb_id = str(movie['id'])

            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': tmdb_id,
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'movie_name': title,
                'original_name': original_name,

                'playable': 'true'
            }, destiny='/play_resolve_movies', folder=False)
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/popular_movies')
        end()
        setview('List')

@route('/trending_movies')
def trending_movies(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.movies_api(page, 'trending')
    if results:
        setcontent('movies')
        for movie in results:
            title = movie.get('title') or movie.get('name')
            year = movie.get('release_date', '')[:4] or movie.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else get_icon('movies')
            fanart = f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else ''
            description = movie.get('overview', '')
            original_name = movie.get('original_title', '')
            tmdb_id = str(movie['id'])

            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': tmdb_id,
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'movie_name': title,
                'original_name': original_name,

                'playable': 'true'
            }, destiny='/play_resolve_movies', folder=False)
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/trending_movies')
        end()
        setview('List')

@route('/premiere_movies')
def premiere_movies(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.movies_api(page, 'premiere')
    if results:
        setcontent('movies')
        for movie in results:
            title = movie.get('title') or movie.get('name')
            year = movie.get('release_date', '')[:4] or movie.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else get_icon('movies')
            fanart = f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path')}" if movie.get('backdrop_path') else ''
            description = movie.get('overview', '')
            original_name = movie.get('original_title', '')
            tmdb_id = str(movie['id'])

            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': tmdb_id,
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'movie_name': title,
                'original_name': original_name,

                'playable': 'true'
            }, destiny='/play_resolve_movies', folder=False)
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/premiere_movies')
        end()
        setview('List')

@route('/popular_tvshows')
def popular_tvshows(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.tv_shows_popular_api(page)
    if results:
        setcontent('tvshows')
        for show in results:
            title = show.get('title') or show.get('name')
            year = show.get('release_date', '')[:4] or show.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else get_icon('tvshows')
            fanart = f"https://image.tmdb.org/t/p/original{show.get('backdrop_path')}" if show.get('backdrop_path') else ''
            description = show.get('overview', '')
            original_name = show.get('original_name', '')
            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': str(show['id']),
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'serie_name': title,
                'original_name': original_name,

            }, destiny='/tvshow_season')
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/popular_tvshows')
        end()
        setview('List')

@route('/trending_tvshows')
def trending_tvshows(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.tv_shows_trending_api(page)
    if results:
        setcontent('tvshows')
        for show in results:
            title = show.get('title') or show.get('name')
            year = show.get('release_date', '')[:4] or show.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else get_icon('tvshows')
            fanart = f"https://image.tmdb.org/t/p/original{show.get('backdrop_path')}" if show.get('backdrop_path') else ''
            description = show.get('overview', '')
            original_name = show.get('original_name', '')
            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': str(show['id']),
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'serie_name': title,
                'original_name': original_name,

            }, destiny='/tvshow_season')
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/trending_tvshows')
        end()
        setview('List')

@route('/premiere_tvshows')
def premiere_tvshows(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.tv_shows_premiere_api(page)
    if results:
        setcontent('tvshows')
        for show in results:
            title = show.get('title') or show.get('name')
            year = show.get('release_date', '')[:4] or show.get('first_air_date', '')[:4]
            icon = f"https://image.tmdb.org/t/p/w500{show.get('poster_path')}" if show.get('poster_path') else get_icon('tvshows')
            fanart = f"https://image.tmdb.org/t/p/original{show.get('backdrop_path')}" if show.get('backdrop_path') else ''
            description = show.get('overview', '')
            original_name = show.get('original_name', '')
            addMenuItem({
                'name': f"{title} ({year})" if year else title,
                'tmdb_id': str(show['id']),
                'year': year,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'serie_name': title,
                'original_name': original_name,

            }, destiny='/tvshow_season')
        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'page': str(page + 1)
            }, destiny='/premiere_tvshows')
        end()
        setview('List')

@route('/popular_anime')
def popular_anime(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.animes_popular_api(page)
    setcontent('tvshows')
    for anime in results:
        title = anime.get('title_english') or anime.get('title')
        original_name = anime.get('title', '')
        year = str(anime.get('year') or '')
        icon = anime.get('images', {}).get('jpg', {}).get('large_image_url') or get_icon('animes')
        fanart = icon
        description = anime.get('synopsis', '')
        addMenuItem({
            'name': title,
            'mal_id': str(anime['mal_id']),
            'year': year,
            'iconimage': icon,
            'fanart': fanart,
            'description': description,
            'anime_name': title,
            'original_name': original_name
        }, destiny='/anime_episodes')
    if page < total_pages:
        addMenuItem({
            'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
            'iconimage': get_icon('next'),
            'page': str(page + 1)
        }, destiny='/popular_anime')
    end()
    setview('List')

@route('/airing_anime')
def airing_anime(param=None):
    param = param or {}
    page = int(param.get('page', 1))
    total_pages, results = httpclient.animes_airing_api(page)
    setcontent('tvshows')
    for anime in results:
        title = anime.get('title_english') or anime.get('title')
        original_name = anime.get('title', '')
        year = str(anime.get('year') or '')
        icon = anime.get('images', {}).get('jpg', {}).get('large_image_url') or get_icon('animes')
        fanart = icon
        description = anime.get('synopsis', '')
        addMenuItem({
            'name': title,
            'mal_id': str(anime['mal_id']),
            'year': year,
            'iconimage': icon,
            'fanart': fanart,
            'description': description,
            'anime_name': title,
            'original_name': original_name
        }, destiny='/anime_episodes')
    if page < total_pages:
        addMenuItem({
            'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
            'iconimage': get_icon('next'),
            'page': str(page + 1)
        }, destiny='/airing_anime')
    end()
    setview('List')

@route('/animes_by_year')
def animes_by_year(param=None):
    param = param or {}
    current_year = datetime.now().year
    setcontent('videos')
    for year in range(current_year, 1962, -1):
        addMenuItem({
            'name': str(year),
            'iconimage': get_icon('premiere'),
            'year': str(year)
        }, destiny='/animes_seasons')
    end()
    setview('WideList')

@route('/animes_seasons')
def animes_seasons(param):
    param = param or {}
    year = param.get('year', '')
    seasons = [
        ('winter', getString(30603)),
        ('spring', getString(30604)),
        ('summer', getString(30605)),
        ('fall', getString(30606))
    ]
    setcontent('videos')
    for season_key, season_name in seasons:
        addMenuItem({
            'name': f'{season_name} {year}',
            'iconimage': get_icon('animes'),
            'anime_season': season_key,
            'year': year
        }, destiny='/animes_by_season')
    end()
    setview('WideList')

@route('/animes_by_season')
def animes_by_season(param):
    param = param or {}
    anime_season = param.get('anime_season', '')
    year = param.get('year', '')
    page = int(param.get('page', 1))

    try:
        total_pages, results = httpclient.animes_by_season_api(year, anime_season, page)
        setcontent('tvshows')

        for anime in results:
            title = anime.get('title_english') or anime.get('title')
            original_name = anime.get('title', '')
            year_anime = str(anime.get('year') or '')
            icon = anime.get('images', {}).get('jpg', {}).get('large_image_url') or get_icon('animes')
            fanart = icon
            description = anime.get('synopsis', '')

            addMenuItem({
                'name': title,
                'mal_id': str(anime['mal_id']),
                'year': year_anime,
                'iconimage': icon,
                'fanart': fanart,
                'description': description,
                'anime_name': title,
                'original_name': original_name
            }, destiny='/anime_episodes')

        if page < total_pages:
            addMenuItem({
                'name': f"[B]{getString(30100)} {page+1} {getString(30101)} {total_pages}[/B]",
                'iconimage': get_icon('next'),
                'anime_season': anime_season,
                'year': year,
                'page': str(page + 1)
            }, destiny='/animes_by_season')

        end()
        setview('List')

    except:
        pass

@route('/play_resolve_movies')
def play_resolve_movies(param):
    param = param or {}
    tmdb_id = param.get('tmdb_id', '')
    year = param.get('year', '')
    movie_name = param.get('movie_name', '')
    original_name = param.get('original_name', '')
    iconimage = param.get('iconimage', get_icon('movies'))
    fanart = param.get('fanart', '')
    description = param.get('description', '')

    loading_manager.show(fanart_path=fanart)

    imdb = ''
    try:
        show_src = httpclient.open_movie_api(tmdb_id)
        if not movie_name:
            movie_name = show_src.get('title', '')
        if not original_name:
            original_name = show_src.get('original_title', '')
        imdb = show_src.get('external_ids', {}).get('imdb_id', '')
    except:
        if not movie_name:
            loading_manager.force_close()
            notify(getString(30805))
            return

    try:
        menus_links = sources.movie_content(tmdb_id, year, movie_name, original_name)
        loading_manager.set_sources_found(len(menus_links))

        if not menus_links:
            loading_manager.force_close()
            notify(getString(30401))
            return

        if is_auto_play_enabled():
            loading_manager.set_phase3()
            stream, sub = try_resolve_with_fallback(
                menus_links,
                lambda url: sources.resolve_movies(url)
            )
            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return
        else:
            player_list = [(name, "") for name, url in menus_links]
            selected_index = loading_manager.set_phase2(player_list)

            if selected_index < 0:
                loading_manager.force_close()
                return

            loading_manager.set_phase3()
            selected_url = menus_links[selected_index][1]

            decoded = unquote(selected_url)
            parsed = urlparse(decoded)
            qs = parse_qs(parsed.query)
            final_url = qs.get('url', [decoded])[0] or qs.get('u', [decoded])[0] or decoded

            stream, sub = sources.resolve_movies(final_url)

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return

        play_item = xbmcgui.ListItem(path=stream)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart})
        play_item.setContentLookup(False)

        stream_lower = stream.lower()
        if '.mpd' in stream_lower:
            play_item.setMimeType('application/dash+xml')
        elif '.m3u8' in stream_lower or 'hls' in stream_lower:
            play_item.setMimeType('application/x-mpegURL')
        elif stream_lower.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts')):
            play_item.setMimeType('video/mp4')

        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(movie_name)
        info_tag.setPlot(description)
        info_tag.setMediaType('movie')
        if year:
            info_tag.setYear(int(year))
        if original_name:
            info_tag.setOriginalTitle(original_name)
        if imdb:
            info_tag.setUniqueIDs({'imdb': imdb}, 'imdb')

        if sub:
            play_item.setSubtitles([sub])

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
        loading_manager.close()

    except Exception as e:
        loading_manager.force_close()
        notify(getString(30304))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())

@route('/tvshow_season')
def tvshow_season(param):
    param = param or {}
    tmdb_id = param.get('tmdb_id', '')
    year = param.get('year', '')
    serie_name = param.get('serie_name', '')

    try:
        show_src = httpclient.open_season_api(tmdb_id)
        if not serie_name:
            serie_name = show_src.get('name', '')
        iconimage = f"https://image.tmdb.org/t/p/w500{show_src.get('poster_path')}" if show_src.get('poster_path') else get_icon('tvshows')
        fanart = f"https://image.tmdb.org/t/p/original{show_src.get('backdrop_path')}" if show_src.get('backdrop_path') else ''
        imdb = show_src.get('external_ids', {}).get('imdb_id', '')
        original_name = show_src.get('original_name', '')

        seasons = show_src.get('seasons', [])
        setcontent('tvshows')
        for season in seasons:
            season_num = season.get('season_number')
            if season_num == 0:
                continue
            season_name = f"{season_num}ª {getString(30601)}"
            season_icon = f"https://image.tmdb.org/t/p/w500{season.get('poster_path')}" if season.get('poster_path') else iconimage

            addMenuItem({
                'name': season_name,
                'iconimage': season_icon,
                'fanart': fanart,
                'description': season.get('overview', ''),
                'tmdb_id': tmdb_id,
                'season_num': str(season_num),
                'year': year,
                'serie_name': serie_name,
                'imdbnumber': imdb,
                'original_name': original_name
            }, destiny='/open_episodes')
        end()
        setview('List')
    except:
        pass

@route('/anime_episodes')
def anime_episodes(param):
    param = param or {}
    mal_id = param.get('mal_id', '')
    year = param.get('year', '')
    anime_name = param.get('anime_name', '')
    iconimage = param.get('iconimage', get_icon('animes'))

    try:
        show_src = httpclient.open_anime_api(mal_id).get('data', {})
        if not anime_name:
            anime_name = show_src.get('title_english') or show_src.get('title', '')
        original_name = param.get('original_name', '') or show_src.get('title', '')
        description = show_src.get('synopsis', '')
        episodes = httpclient.open_anime_episodes_api(mal_id)
        anime_type = show_src.get('type', '')
        fanart = iconimage

        if anime_type == 'Movie':
            setcontent('movies')
            addMenuItem({
                'name': anime_name,
                'mal_id': mal_id,
                'video_title': anime_name,
                'iconimage': iconimage,
                'fanart': fanart,
                'description': description,
                'year': year,
                'playable': 'true'
            }, destiny='/play_resolve_anime_movies', folder=False)
            end()
            return

        setcontent('episodes')
        today = datetime.today().date()
        db_instance = get_kodi_service()
        watched_set = db_instance.get_watched_anime_episodes(mal_id)
        resume_map = db_instance.get_resume_times_anime(mal_id)

        for episode in episodes:
            aired = episode.get('aired')
            if aired:
                try:
                    air_date_obj = datetime.strptime(aired.split('T')[0], "%Y-%m-%d").date()
                    if air_date_obj > today:
                        continue
                except:
                    pass
            epnum = episode.get('mal_id')
            ep_name = episode.get('title') or f"{anime_name} {epnum}"
            icon = episode.get('images', {}).get('jpg', {}).get('image_url') or iconimage
            name = f"Ep {int(epnum):02d} {ep_name}"
            addMenuItem({
                'name': name,
                'description': episode.get('synopsis') or description,
                'iconimage': icon,
                'fanart': fanart,
                'mal_id': mal_id,
                'episode_num': str(epnum),
                'anime_name': anime_name,
                'original_name': original_name,
                'episode_title': ep_name,
                'mediatype': 'episode',
                'playable': 'true',
                'playcount': 1 if int(epnum) in watched_set else 0,
                'resume_time': resume_map.get(int(epnum))
            }, destiny='/play_resolve_animes', folder=False)
        setview('InfoWall')
        end()
    except:
        notify(getString(30406))

@route('/open_episodes')
def open_episodes(param):
    param = param or {}
    tmdb_id = param.get('tmdb_id', '')
    season_num = param.get('season_num', '')
    year = param.get('year', '')
    serie_name = param.get('serie_name', '')
    imdb = param.get('imdbnumber', '')
    original_name = param.get('original_name', '')

    try:
        show_src = httpclient.open_season_api(tmdb_id)
        if not serie_name:
            serie_name = show_src.get('name', '')
        if not imdb:
            imdb = show_src.get('external_ids', {}).get('imdb_id', '')

        src = httpclient.show_episode_api(tmdb_id, season_num, imdb_id=imdb)

        iconimage = f"https://image.tmdb.org/t/p/w500{show_src.get('poster_path')}" if show_src.get('poster_path') else get_icon('tvshows')
        serie_fanart = f"https://image.tmdb.org/t/p/original{show_src.get('backdrop_path')}" if show_src.get('backdrop_path') else ''

        today = datetime.now().date()

        db_instance = get_kodi_service()
        watched_set = db_instance.get_watched_tvshow_in_season(tmdb_id, int(season_num))
        resume_map = db_instance.get_resume_times_tvshow_season(tmdb_id, int(season_num))


        setcontent('episodes')
        for episode in src.get('episodes', []):
            air_date = episode.get('air_date')
            if air_date:
                try:
                    air_date_obj = datetime.strptime(air_date, "%Y-%m-%d").date()
                    if air_date_obj > today:
                        continue
                except:
                    pass

            episode_num = str(episode.get('episode_number'))
            ep_name = episode.get('name', f"{serie_name} {episode_num}")
            icon = f"https://image.tmdb.org/t/p/w500{episode.get('still_path')}" if episode.get('still_path') else get_icon('tvshows')
            description = episode.get('overview', show_src.get('overview', ''))

            addMenuItem({
                'name': f"{int(season_num)}x{int(episode_num):02d} {ep_name}",
                'description': description,
                'iconimage': icon,
                'fanart': serie_fanart,
                'tmdb_id': tmdb_id,
                'season_num': season_num,
                'episode_num': episode_num,
                'imdbnumber': imdb,
                'serie_name': serie_name,
                'original_name': original_name,
                'episode_title': ep_name,
                'mediatype': 'episode',
                'playable': 'true',
                'playcount': 1 if int(episode_num) in watched_set else 0,
                'resume_time': resume_map.get(int(episode_num))
            }, destiny='/play_resolve_tvshows', folder=False)
        setview('InfoWall')
        end()
    except:
        pass

@route('/play_resolve_tvshows')
def play_resolve_tvshows(param):
    param = param or {}
    serie_name = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    tmdb_id = param.get('tmdb_id', '')
    imdb = param.get('imdb', '') or param.get('imdbnumber', '')
    season_num = param.get('season_num', '')
    episode_num = param.get('episode_num', '')
    episode_title = param.get('episode_title', '')
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', '') or iconimage
    description = param.get('description', '')
    from_upnext = param.get('from_upnext', 'false')

    if not season_num or not episode_num:
        notify(getString(30800))
        return

    try:
        season_num = int(season_num)
        episode_num = int(episode_num)
    except:
        notify(getString(30801))
        return

    db = get_kodi_service()
    _rt = db.get_resume_time_tvshow(tmdb_id, season_num, episode_num)
    resume_time = None
    if _rt and _rt[0] > 0:
        if ask_resume(_rt[0]):
            resume_time = _rt[0]
        else:
            db.clear_resume_time_tvshow(tmdb_id, season_num, episode_num)

    loading_manager.show(fanart_path=fanart)

    try:
        stream = None
        sub = None

        menus_links = sources.show_content(tmdb_id, season_num, episode_num, serie_name, original_name)
        loading_manager.set_sources_found(len(menus_links))

        if not menus_links:
            loading_manager.force_close()
            notify(getString(30401))
            return

        if is_auto_play_enabled():
            loading_manager.set_phase3()

            stream, sub = try_resolve_with_fallback(
                menus_links,
                lambda url: sources.resolve_tvshows(url)
            )

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return
        else:
            player_list = [(name, "") for name, url in menus_links]
            selected_index = loading_manager.set_phase2(player_list)

            if selected_index < 0:
                loading_manager.force_close()
                return

            loading_manager.set_phase3()
            selected_url = menus_links[selected_index][1]

            decoded = unquote(selected_url)
            parsed = urlparse(decoded)
            qs = parse_qs(parsed.query)
            final_url = qs.get('url', [decoded])[0] or qs.get('u', [decoded])[0] or decoded

            stream, sub = sources.resolve_tvshows(final_url)

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return

        play_item = xbmcgui.ListItem(path=stream)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart})
        play_item.setContentLookup(False)

        stream_lower = stream.lower()
        if '.mpd' in stream_lower:
            play_item.setMimeType('application/dash+xml')
        elif '.m3u8' in stream_lower or 'hls' in stream_lower:
            play_item.setMimeType('application/x-mpegURL')
        elif stream_lower.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts')):
            play_item.setMimeType('video/mp4')

        showtitle = serie_name

        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(episode_title)
        info_tag.setTvShowTitle(showtitle)
        info_tag.setPlot(description)
        info_tag.setMediaType('episode')
        info_tag.setSeason(season_num)
        info_tag.setEpisode(episode_num)
        if original_name:
            info_tag.setOriginalTitle(original_name)
        if tmdb_id:
            info_tag.setUniqueIDs({'tmdb': tmdb_id}, 'tmdb')

        if sub:
            play_item.setSubtitles([sub])

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)

        loading_manager.close()

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        if playlist.size() <= 1:
            all_episodes = db.get_tvshow_season_episodes(tmdb_id, season_num)
            if all_episodes:
                build_tvshow_playlist(
                    tmdb_id=tmdb_id,
                    season_num=season_num,
                    current_episode_num=episode_num,
                    serie_name=serie_name,
                    original_name=original_name,
                    all_episodes=all_episodes,
                    imdb_id=imdb
                )

        xbmcgui.Window(10000).setProperty(WINDOW_PROP, json.dumps({
            'kind': 'tvshow',
            'content_id': str(tmdb_id),
            'season': season_num,
            'episode': episode_num,
            'resume_time': resume_time,
        }))

    except Exception as e:
        loading_manager.force_close()
        notify(getString(30304))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
        xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()

@route('/play_resolve_animes')
def play_resolve_animes(param):
    param = param or {}
    mal_id = param.get('mal_id', '')
    episode_num = param.get('episode_num', '')
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', iconimage)
    description = param.get('description', '')
    anime_name = param.get('anime_name', '')
    original_name = param.get('original_name', '')
    episode_title = param.get('episode_title', '')
    from_upnext = param.get("from_upnext", "false")

    if not mal_id or not episode_num:
        notify(getString(30800))
        return

    try:
        episode_num = int(episode_num)
    except:
        notify(getString(30801))
        return

    db = get_kodi_service()
    _rt = db.get_resume_time_anime(mal_id, episode_num)
    resume_time = None
    if _rt and _rt[0] > 0:
        if ask_resume(_rt[0]):
            resume_time = _rt[0]
        else:
            db.clear_resume_time_anime(mal_id, episode_num)

    loading_manager.show(fanart_path=fanart)

    try:
        stream = None
        sub = None

        menus_links = sources.show_content_anime(mal_id, episode_num, anime_name, original_name)
        loading_manager.set_sources_found(len(menus_links))

        if not menus_links:
            loading_manager.force_close()
            notify(getString(30401))
            return

        if is_auto_play_enabled():
            loading_manager.set_phase3()

            stream, sub = try_resolve_with_fallback(
                menus_links,
                lambda url: sources.resolve_animes(url)
            )

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return
        else:
            player_list = [(name, "") for name, url in menus_links]
            selected_index = loading_manager.set_phase2(player_list)

            if selected_index < 0:
                loading_manager.force_close()
                return

            loading_manager.set_phase3()
            selected_url = menus_links[selected_index][1]

            decoded = unquote(selected_url)
            parsed = urlparse(decoded)
            qs = parse_qs(parsed.query)
            final_url = qs.get('url', [decoded])[0] or qs.get('u', [decoded])[0] or decoded

            stream, sub = sources.resolve_animes(final_url)

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
                return

        stop_player()

        if not episode_title:
            episode_title = f"Ep {episode_num}"

        play_item = xbmcgui.ListItem(path=stream)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart})
        play_item.setContentLookup(False)

        stream_lower = stream.lower()
        if '.mpd' in stream_lower:
            play_item.setMimeType('application/dash+xml')
        elif '.m3u8' in stream_lower or 'hls' in stream_lower:
            play_item.setMimeType('application/x-mpegURL')
        elif stream_lower.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts')):
            play_item.setMimeType('video/mp4')

        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(episode_title)
        info_tag.setTvShowTitle(anime_name)
        info_tag.setPlot(description)
        info_tag.setMediaType('episode')
        info_tag.setSeason(1)
        info_tag.setEpisode(episode_num)
        if original_name:
            info_tag.setOriginalTitle(original_name)

        if sub:
            play_item.setSubtitles([sub])

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)

        loading_manager.close()

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        if playlist.size() <= 1:
            all_episodes = db.get_anime_all_episodes(mal_id)
            if all_episodes:
                build_anime_playlist(
                    mal_id=mal_id,
                    current_episode_num=episode_num,
                    anime_name=anime_name,
                    original_name=original_name,
                    all_episodes=all_episodes
                )

        xbmcgui.Window(10000).setProperty(WINDOW_PROP, json.dumps({
            'kind': 'anime',
            'content_id': str(mal_id),
            'season': 0,
            'episode': episode_num,
            'resume_time': resume_time,
        }))

    except Exception as e:
        loading_manager.force_close()
        notify(getString(30304))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
        xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()

@route('/play_resolve_anime_movies')
def play_resolve_anime_movies(param):
    param = param or {}
    mal_id = param.get('mal_id', '')
    year = param.get('year', '')
    anime_name = param.get('anime_name', '')
    original_name = param.get('original_name', '')
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', iconimage)
    description = param.get('description', '')
    loading_manager.show(fanart_path=fanart)

    try:
        menus_links = sources.movie_content_anime(mal_id, anime_name, original_name, year)
        loading_manager.set_sources_found(len(menus_links))

        if not menus_links:
            loading_manager.force_close()
            notify(getString(30401))
            return

        if is_auto_play_enabled():
            loading_manager.set_phase3()
            stream, sub = try_resolve_with_fallback(
                menus_links,
                lambda url: sources.resolve_anime_movies(url)
            )
            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                return
        else:
            player_list = [(name, "") for name, url in menus_links]
            selected_index = loading_manager.set_phase2(player_list)

            if selected_index < 0:
                loading_manager.force_close()
                return

            loading_manager.set_phase3()
            selected_url = menus_links[selected_index][1]

            decoded = unquote(selected_url)
            parsed = urlparse(decoded)
            qs = parse_qs(parsed.query)
            final_url = qs.get('url', [decoded])[0] or qs.get('u', [decoded])[0] or decoded

            stream, sub = sources.resolve_anime_movies(final_url)

            if not stream:
                loading_manager.force_close()
                notify(getString(30402))
                return

        stop_player()

        play_item = xbmcgui.ListItem(path=stream)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart})
        play_item.setContentLookup(False)

        stream_lower = stream.lower()
        if '.mpd' in stream_lower:
            play_item.setMimeType('application/dash+xml')
        elif '.m3u8' in stream_lower or 'hls' in stream_lower:
            play_item.setMimeType('application/x-mpegURL')
        elif stream_lower.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts')):
            play_item.setMimeType('video/mp4')

        tag = play_item.getVideoInfoTag()
        tag.setTitle(anime_name)
        tag.setPlot(description)
        tag.setMediaType('movie')
        if year:
            tag.setYear(int(year))
        if original_name:
            tag.setOriginalTitle(original_name)

        if sub:
            play_item.setSubtitles([sub])

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
        loading_manager.close()

    except Exception as e:
        loading_manager.force_close()
        notify(getString(30304))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
