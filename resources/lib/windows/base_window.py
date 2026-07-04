# -*- coding: utf-8 -*-

import xbmc
import xbmcgui


class BaseWindow(xbmcgui.WindowXMLDialog):

    def __init__(self, xml_file, location, actionArgs=None):
        self.actionArgs = actionArgs or {}

        fanart_path = self.actionArgs.get('fanart_path', '')
        if fanart_path:
            xbmcgui.Window(10000).setProperty('loading.fanart', fanart_path)

        super().__init__(xml_file, location)

        try:
            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
            xbmc.executebuiltin('Dialog.Close(busydialog)')
        except:
            pass

    def close(self, clear_properties=True):
        if clear_properties:
            self._clear_window_properties()
        super().close()

    def _clear_window_properties(self):
        pass
