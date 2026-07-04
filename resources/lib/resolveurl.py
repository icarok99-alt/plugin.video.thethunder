# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon
import os
import sys
import urllib.request
import zipfile
import shutil

try:
    _addon = xbmcaddon.Addon()
except RuntimeError:
    _addon = xbmcaddon.Addon('plugin.video.thethunder')

def getString(string_id):
    return _addon.getLocalizedString(string_id)

def download_and_install(url, name):
    dialog = xbmcgui.DialogProgress()
    dialog.create(getString(30808), '{} {}...'.format(getString(30802), name))

    addon_path = xbmcvfs.translatePath('special://home/addons/')
    temp_zip = os.path.join(addon_path, 'temp_resolveurl.zip')

    correct_path = os.path.join(addon_path, 'script.module.resolveurl.fork')
    wrong_path = os.path.join(addon_path, 'script.module.resolveurl-main')

    try:
        urllib.request.urlretrieve(url, temp_zip)
        dialog.update(50, getString(30803))

        if os.path.exists(correct_path):
            shutil.rmtree(correct_path)

        if os.path.exists(wrong_path):
            shutil.rmtree(wrong_path)

        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(addon_path)

        if os.path.exists(wrong_path):
            os.rename(wrong_path, correct_path)

        if os.path.exists(temp_zip):
            os.remove(temp_zip)

        dialog.update(100, getString(30804))

        xbmcgui.Dialog().ok(
            getString(30808),
            getString(30807)
        )

    except Exception as e:
        xbmcgui.Dialog().ok(getString(30805), '{}:\n{}'.format(getString(30806), str(e)))

    finally:
        dialog.close()

def update():
    url = 'https://github.com/icarok99-alt/script.module.resolveurl/archive/refs/heads/main.zip'
    download_and_install(url, 'ResolveURL')

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'update':
        update()
    else:
        update()
