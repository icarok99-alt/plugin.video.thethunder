# -*- coding: utf-8 -*-

import os
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib.windows.loading_window import LoadingWindow
from resources.lib.windows.source_select import SourceSelect


class _PlaybackMonitor(xbmc.Player):

    def __init__(self):
        super().__init__()
        self._event = threading.Event()

    def onPlayBackStarted(self):
        self._event.set()

    def onAVStarted(self):
        self._event.set()

    def onPlayBackError(self):
        self._event.set()

    def onPlayBackStopped(self):
        self._event.set()

    def reset(self):
        self._event.clear()

    def wait_for_playback(self, timeout=20):
        monitor = xbmc.Monitor()
        elapsed = 0
        interval = 0.2

        while elapsed < timeout:
            if self._event.is_set():
                return True
            try:
                if self.isPlaying() and self.getTime() > 0:
                    return True
            except:
                pass
            if monitor.waitForAbort(interval):
                return False
            elapsed += interval

        return False


class LoadingManager:

    def __init__(self):
        self.window = None
        self.addon = xbmcaddon.Addon()
        self.addon_path = self.addon.getAddonInfo('path')
        self._lock = threading.Lock()

        self._anim_thread = None
        self._anim_running = False

        self._monitor_thread = None
        self._busy_suppress_thread = None
        self._suppress_busy = False
        self._should_close = False
        self._player_monitor = _PlaybackMonitor()

        self._default_fanart = os.path.join(
            self.addon_path, 'resources', 'images', 'fanart.jpg'
        )

    def _run_animation(self):
        try:
            while self._anim_running:
                for i in range(0, 101, 2):
                    if not self._anim_running:
                        break
                    xbmcgui.Window(10000).setProperty('loading.progress', str(i))
                    time.sleep(0.06)
                if self._anim_running:
                    time.sleep(0.2)
        except:
            pass

    def _start_animation(self):
        if self._anim_thread is None or not self._anim_thread.is_alive():
            self._anim_running = True
            self._anim_thread = threading.Thread(target=self._run_animation)
            self._anim_thread.daemon = True
            self._anim_thread.start()

    def _stop_animation(self):
        self._anim_running = False
        xbmcgui.Window(10000).clearProperty('loading.progress')

    def _run_busy_suppressor(self):
        try:
            while self._suppress_busy:
                xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
                xbmc.executebuiltin('Dialog.Close(busydialog)')
                xbmc.sleep(100)
        except:
            pass

    def _ensure_busy_suppressor(self):
        if not self._suppress_busy:
            self._suppress_busy = True
        if self._busy_suppress_thread is None or not self._busy_suppress_thread.is_alive():
            self._busy_suppress_thread = threading.Thread(target=self._run_busy_suppressor)
            self._busy_suppress_thread.daemon = True
            self._busy_suppress_thread.start()

    def show(self, fanart_path=None):
        with self._lock:
            try:
                if not fanart_path:
                    fanart_path = self._default_fanart

                xbmcgui.Window(10000).setProperty('loading.fanart', fanart_path)

                self._should_close = False
                self._player_monitor.reset()

                xbmcgui.Window(10000).setProperty('loading.sources_found', '')
                xbmcgui.Window(10000).setProperty('loading.phase', '1')

                if self.window is None:
                    self.window = LoadingWindow(
                        'DialogLoading.xml',
                        self.addon_path,
                        actionArgs={'fanart_path': fanart_path}
                    )
                    self.window.show()

                self._start_animation()
                self._ensure_busy_suppressor()

            except:
                pass

    def set_sources_found(self, count):
        try:
            if count > 0:
                text = f"{count} fonte{'s' if count != 1 else ''}"
            else:
                text = ""
            xbmcgui.Window(10000).setProperty('loading.sources_found', text)
        except:
            pass

    def set_phase2(self, player_list):
        try:
            fanart = xbmcgui.Window(10000).getProperty('loading.fanart')

            select_window = SourceSelect(
                'DialogSourceSelect.xml',
                self.addon_path,
                actionArgs={'fanart_path': fanart, 'player_list': player_list}
            )

            selected_index = select_window.doModal()

            xbmcgui.Window(10000).setProperty('loading.phase', '3')

            return selected_index

        except:
            return -1

    def set_phase3(self):
        try:
            xbmcgui.Window(10000).setProperty('loading.phase', '3')
            self._ensure_busy_suppressor()
        except:
            pass

    def close(self):
        if self.window:
            self._should_close = True
            if self._monitor_thread is None or not self._monitor_thread.is_alive():
                self._player_monitor.reset()
                self._monitor_thread = threading.Thread(target=self._wait_for_playback)
                self._monitor_thread.daemon = True
                self._monitor_thread.start()

    def _wait_for_playback(self):
        self._player_monitor.wait_for_playback(timeout=20)
        self._do_close()

    def _do_close(self):
        with self._lock:
            if self.window and self._should_close:
                try:
                    self._suppress_busy = False
                    self._stop_animation()
                    self.window.close(clear_properties=True)
                    self.window = None
                except:
                    pass

    def force_close(self):
        with self._lock:
            self._suppress_busy = False
            self._should_close = False
            self._stop_animation()
            if self.window:
                try:
                    self.window.close(clear_properties=True)
                except:
                    pass
                self.window = None
            xbmcgui.Window(10000).clearProperty('loading.fanart')


loading_manager = LoadingManager()
