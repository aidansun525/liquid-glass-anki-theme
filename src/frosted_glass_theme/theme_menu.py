"""Tools → Frosted Glass: the few things you reach for often, plus Settings."""

import os

from aqt import gui_hooks, mw
from aqt.qt import QAction, QKeySequence, QMenu
from aqt.utils import openFolder, showInfo

from . import background, frosted_glass, migrate, wallpaper_fetcher
from .settings_window import open_settings

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


def _action(menu, label, fn, shortcut=None):
    action = QAction(label, mw)
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    action.triggered.connect(lambda _checked=False: fn())
    menu.addAction(action)
    return action


def build():
    menu = QMenu("Frosted Glass", mw)
    _action(menu, "New wallpaper", background.next_wallpaper, "Ctrl+Shift+W")
    wallpaper_fetcher.add_menu_items(menu)
    menu.addSeparator()
    frosted_glass.add_menu_items(menu)
    menu.addSeparator()
    _action(menu, "Settings…", open_settings)
    _action(menu, "Open add-on files folder", lambda: openFolder(os.path.join(ADDON_DIR, "user_files")))
    mw.form.menuTools.addMenu(menu)


_shown = False


def _first_run_note():
    global _shown
    if _shown:
        return
    _shown = True
    note = migrate.message()
    if note:
        showInfo(note, title="Frosted Glass")


build()
gui_hooks.main_window_did_init.append(_first_run_note)
