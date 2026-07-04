# -*- coding: utf-8 -*-

import xbmc
import xbmcgui

from resources.lib.windows.base_window import BaseWindow


class SourceSelect(BaseWindow):

    PLAYER_LIST_CONTROL = 200

    def __init__(self, xml_file, location, actionArgs=None):
        super().__init__(xml_file, location, actionArgs)
        self.player_list = self.actionArgs.get('player_list', [])
        self.selected_index = -1
        self.display_list = None

    def onInit(self):
        try:
            self.display_list = self.getControl(self.PLAYER_LIST_CONTROL)
            self.display_list.reset()

            for idx, (player_name, player_info) in enumerate(self.player_list):
                item = xbmcgui.ListItem(player_name, offscreen=True)
                item.setLabel2(player_info)
                self.display_list.addItem(item)

            self.setFocusId(self.PLAYER_LIST_CONTROL)

        except Exception as e:
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)

    def onClick(self, controlId):
        if controlId == self.PLAYER_LIST_CONTROL:
            try:
                self.selected_index = self.display_list.getSelectedPosition()
            except:
                self.selected_index = -1
            self.close()

    def onAction(self, action):
        if action.getId() in [92, 10]:
            self.selected_index = -1
            self.close()

    def doModal(self):
        super(SourceSelect, self).doModal()
        return self.selected_index

    def close(self):
        self.display_list = None
        super().close()
