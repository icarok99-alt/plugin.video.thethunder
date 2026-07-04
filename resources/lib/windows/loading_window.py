# -*- coding: utf-8 -*-

import xbmc
import xbmcgui

from resources.lib.windows.base_window import BaseWindow


class LoadingWindow(BaseWindow):

    def __init__(self, xml_file, location, actionArgs=None):
        super().__init__(xml_file, location, actionArgs)
        self.canceled = False

    def onAction(self, action):
        if action.getId() in [92, 10]:
            self.canceled = True
            self.close()

    def _clear_window_properties(self):
        xbmcgui.Window(10000).clearProperty('loading.progress')
        xbmcgui.Window(10000).clearProperty('loading.sources_found')
        xbmcgui.Window(10000).clearProperty('loading.phase')
