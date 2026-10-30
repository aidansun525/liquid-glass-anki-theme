"""
Background (part of Frosted Glass)
--------------------------------------
Draws a wallpaper from user_files/background behind the deck list, deck
overview, review screen and the top/bottom bars, and can swap the deck
gear icon.

Changes are applied live by swapping one <style> element in each open
screen, so moving a slider or picking a new wallpaper never reloads
anything.

Based on Custom Background Image and Gear Icon by ijgnd and The AnKing
(GNU AGPL v3 or later); see README.txt.
"""

import json
import os
import random

from aqt import gui_hooks, mw
from aqt.qt import QEvent, QObject, QPoint, QTimer
from aqt.deckbrowser import DeckBrowser, DeckBrowserBottomBar
from aqt.overview import Overview, OverviewBottomBar
from aqt.reviewer import Reviewer, ReviewerBottomBar
from aqt.toolbar import BottomToolbar, TopToolbar

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.basename(ADDON_DIR)
USER_FILES = os.path.join(ADDON_DIR, "user_files")
BG_DIR = os.path.join(USER_FILES, "background")
GEAR_DIR = os.path.join(USER_FILES, "gear")
CSS_DIR = os.path.join(USER_FILES, "css")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")
ANKI_GEAR = "gears.svg"
HIDDEN = {"anking.png", "gears.svg"}  # old branding, and Anki's own gear (listed separately)
STYLE_ID = "ast-bg"

DEFAULTS = {
    "Image name for background": "random",
    "Image name for gear": ANKI_GEAR,
    "Reviewer image": True,
    "Toolbar image": True,
    "Toolbar top/bottom": True,
    "background-attachment": "fixed",
    "background-color bottom": "",
    "background-color main": "",
    "background-color top": "",
    "background opacity main": "1",
    "background opacity review": "1",
    "background-position": "center",
    "background scale": "1",
    "background-size": "cover",
    "New wallpaper on each visit to the deck list": False,
}


# ---------------------------------------------------------------- config

def get_config():
    cfg = dict(DEFAULTS)
    cfg.update(mw.addonManager.getConfig(ADDON) or {})
    return cfg


def save_config(cfg):
    mw.addonManager.writeConfig(ADDON, cfg)


def _num(value, default, lo, hi):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- pictures

def _list(folder):
    try:
        names = os.listdir(folder)
    except FileNotFoundError:
        return []
    return sorted(n for n in names
                  if (n.lower().endswith(IMAGE_EXT) or _is_photo_note(n)) and n.lower() not in HIDDEN
                  and os.path.isfile(os.path.join(folder, n)))


def _is_photo_note(name):
    from . import wallpaper_fetcher as wf
    return name.startswith(wf.UNSPLASH_PREFIX) and name.endswith(".json")


def wallpapers():
    """Your own pictures, the built-in ones, and the downloads of the style
    picked in Settings (Professional or Anime)."""
    from . import wallpaper_fetcher as wf
    which = wf.style()
    return [p for p in _list(BG_DIR)
            if not p.startswith(wf.PREFIX) or wf.is_style_download(p, which)]


def gears():
    return _list(GEAR_DIR)


_current = None


def current_wallpaper(cfg=None):
    """The picture on screen now. 'random' picks once, then sticks until
    you ask for a new one (or return to the deck list, if enabled)."""
    global _current
    choice = (cfg or get_config())["Image name for background"]
    pics = wallpapers()
    if choice and choice.lower() != "random":
        if choice in pics:
            _current = choice  # so Shuffle carries on from the picture on screen
            return choice
        # the chosen picture is gone (deleted, or not part of the current style): shuffle instead
    if _current not in pics:
        _current = random.choice(pics) if pics else None
    return _current or ""


# called after the wallpaper changes, e.g. so an open Settings window can follow
on_wallpaper_changed = []


def recheck_wallpaper():
    """After the wallpaper style changes: if the picture on screen
    no longer fits, swap it everywhere right away."""
    if _current is not None and _current not in wallpapers():
        next_wallpaper()
    else:
        apply_live()


def next_wallpaper():
    """Pick a different random wallpaper and show it everywhere right away."""
    global _current
    on_screen = current_wallpaper()
    cfg = get_config()
    if str(cfg["Image name for background"]).lower() != "random":
        cfg["Image name for background"] = "random"
        save_config(cfg)
    pics = wallpapers()
    others = [p for p in pics if p != on_screen] or pics
    _current = random.choice(others) if others else None
    apply_live()
    for fn in list(on_wallpaper_changed):
        fn()
    return _current


def current_gear():
    val = get_config()["Image name for gear"]
    if not val or val == ANKI_GEAR or val.lower() in HIDDEN:
        return None
    pics = gears()
    if val.lower() == "random":
        return random.choice(pics) if pics else None
    return val if val in pics else None


# ---------------------------------------------------------------- css

def _url(folder, name):
    return f"/_addons/{ADDON}/user_files/{folder}/{name}"


_notes = {}


def photo_note(name):
    """The saved details (address, credit) of an Unsplash photo, or None."""
    if not name or not _is_photo_note(name):
        return None
    if name not in _notes:
        from . import wallpaper_fetcher as wf
        _notes[name] = wf.read_unsplash(os.path.join(BG_DIR, name))
    return _notes[name]


def picture_url(name):
    """Where a wallpaper is loaded from: a file in user_files/background, or
    (for Unsplash photos) Unsplash itself."""
    note = photo_note(name)
    if note:
        return note["url"]
    return _url("background", name)


def _fallback():
    """A built-in picture shown under an Unsplash photo while offline."""
    for name in _list(BG_DIR):
        if name.startswith("Default"):
            return _url("background", name)
    return None


def thumbnail_path(name):
    note = photo_note(name)
    if note:
        from . import wallpaper_fetcher as wf
        return os.path.join(wf.THUMB_DIR, name[:-5] + ".jpg")
    return os.path.join(BG_DIR, name)


def _dim_color(alpha):
    """Anki's window color for the current theme, with the given alpha."""
    from aqt.theme import theme_manager
    hexcolor = "#2c2c2c" if theme_manager.night_mode else "#f5f5f5"
    try:
        from aqt import colors
        hexcolor = colors.CANVAS["dark" if theme_manager.night_mode else "light"]
    except Exception:
        pass
    h = hexcolor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def css_for(screen, cfg=None):
    """screen: main, review, top or bottom."""
    cfg = cfg or get_config()
    if screen == "review" and not cfg["Reviewer image"]:
        return "body::before { background-image: none !important; }"
    if screen in ("top", "bottom") and not cfg["Toolbar image"]:
        return ""
    name = current_wallpaper(cfg)
    # the bars match whatever the main screen shows, so they blend into it
    reviewing = screen == "review" or (screen in ("top", "bottom") and mw.state == "review")
    opacity = _num(cfg["background opacity review" if reviewing else "background opacity main"], 1, 0, 1)
    scale = _num(cfg["background scale"], 1, 0.5, 3)
    position = cfg["background-position"] or "center"
    color = cfg["background-color top" if screen == "top" else
                "background-color bottom" if screen == "bottom" else "background-color main"]
    image = f'url("{picture_url(name)}")' if name else "none"
    size = cfg["background-size"] or "cover"
    fallback = _fallback() if photo_note(name) else None
    if fallback and size == "cover":
        # if Unsplash can't be reached (offline), a built-in picture shows instead
        image = f'{image}, url("{fallback}")'
        size = f"{size}, {size}"
        position = f"{position}, {position}"
    if name and opacity < 1:
        # Dim with a layer of the window color drawn over the picture, rather
        # than by fading the picture into whatever is behind it. Each bar is a
        # separate page with its own backdrop, so fading looked different on
        # each (the top bar stayed bright in dark mode); this looks the same everywhere.
        dim = _dim_color(1 - opacity)
        image = f"linear-gradient({dim}, {dim}), {image}"
        size = f"100% 100%, {size}"
        position = f"0 0, {position}"
        opacity = 1
    css = f"""
body::before {{
  content: ""; position: fixed; z-index: -99; pointer-events: none;
  left: 0; top: var(--ast-y, 0px); width: var(--ast-w, 100vw); height: var(--ast-h, 100vh);
  background-image: {image};
  background-size: {size};
  background-repeat: no-repeat;
  background-position: {position};
  {f"background-color: {color} !important;" if color else ""}
  opacity: {opacity:g};
  transform: scale({scale:g});
  will-change: transform;
  transition: background-image .5s ease, opacity .3s ease;
}}"""
    if screen == "main":
        css += CREDIT_CSS
        css += """
.fancy table { backdrop-filter: none; }
.current td, tr:hover:not(.top-level-drag-row) td { background: #e4e4e4ad; }
.nightMode .current td, .nightMode tr:hover:not(.top-level-drag-row) td { background: #2c2c2fad; }"""
        if current_gear():
            css += "\n.nightMode .gears { filter: none; }"
    return css


def _screen_for(context):
    if isinstance(context, (DeckBrowser, Overview)):
        return "main"
    if isinstance(context, Reviewer):
        return "review"
    if isinstance(context, TopToolbar):
        return "top"
    if isinstance(context, (BottomToolbar, DeckBrowserBottomBar, OverviewBottomBar, ReviewerBottomBar)):
        return "bottom"
    return None


CUSTOM_CSS = {"main": ("deckbrowser", "overview"), "review": ("reviewer",),
              "top": ("toolbar",), "bottom": ("toolbar-bottom", "reviewer-bottom")}


def _custom_css(screen):
    """Your own CSS from user_files/css/custom_<page>.css, if any."""
    out = ""
    for page in CUSTOM_CSS[screen]:
        try:
            with open(os.path.join(CSS_DIR, f"custom_{page}.css"), encoding="utf-8") as f:
                out += f.read() + "\n"
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- one picture across all three views
# The top bar, main screen and bottom bar are three separate web views. Each
# one draws the wallpaper sized to the whole window and shifted up by its own
# offset, so the three pieces line up into one seamless picture.

def _views():
    return [w for w in (getattr(mw, "toolbarWeb", None), getattr(mw, "web", None), getattr(mw, "bottomWeb", None)) if w]


def _geometry_vars(web):
    shown = [w for w in _views() if w.isVisible() and w.height() > 0] or [web]
    tops = [w.mapTo(mw, QPoint(0, 0)).y() for w in shown]
    area_top = min(tops)
    area_bottom = max(t + w.height() for t, w in zip(tops, shown))
    zoom = web.zoomFactor() or 1
    y = web.mapTo(mw, QPoint(0, 0)).y() - area_top
    return {"--ast-y": f"{-y / zoom:.1f}px", "--ast-w": f"{web.width() / zoom:.1f}px",
            "--ast-h": f"{(area_bottom - area_top) / zoom:.1f}px"}


def _vars_css(web):
    try:
        return ":root{" + "".join(f"{k}:{v};" for k, v in _geometry_vars(web).items()) + "}"
    except Exception:
        return ""


def sync_geometry():
    for web in _views():
        try:
            js = ";".join(f"document.documentElement.style.setProperty({json.dumps(k)},{json.dumps(v)})"
                          for k, v in _geometry_vars(web).items())
            web.eval(js)
        except Exception:
            pass


class _GeometryWatcher(QObject):
    """Re-aligns the pieces whenever a view moves or resizes (window resize,
    bottom bar growing, top bar hiding during review, ...)."""

    def __init__(self):
        super().__init__(mw)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(sync_geometry)
        self.watched = set()

    def watch(self):
        for web in _views():
            if id(web) not in self.watched:
                web.installEventFilter(self)
                self.watched.add(id(web))

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.Hide):
            self.timer.start(30)
        return False


_watcher = None


def on_main_window_ready():
    global _watcher
    _watcher = _GeometryWatcher()
    _watcher.watch()


CREDIT_CSS = """
#ast-credit { position: fixed; right: 10px; bottom: 6px; z-index: 5; font-size: 11px;
  color: rgba(255,255,255,.72); text-shadow: 0 1px 2px rgba(0,0,0,.6); opacity: .8; }
#ast-credit a { color: inherit; text-decoration: none; cursor: pointer; }
#ast-credit a:hover { text-decoration: underline; }
#ast-credit:empty { display: none; }"""


def credit_html(name):
    """Unsplash requires crediting the photographer while their photo is shown."""
    note = photo_note(name)
    if not note:
        return ""
    import html
    c = note.get("credit") or {}
    def link(url, text):
        return (f"<a onclick='pycmd({html.escape(json.dumps('ast:open:' + str(url)))});return false;'>"
                f"{html.escape(str(text))}</a>")
    return f"Photo by {link(c.get('profile', ''), c.get('name', 'Unknown'))} on {link(c.get('unsplash', ''), 'Unsplash')}"


def _credit_js(name):
    inner = json.dumps(credit_html(name))
    return ("(function(){var c=document.getElementById('ast-credit');"
            "if(!c){c=document.createElement('div');c.id='ast-credit';document.body.appendChild(c);}"
            f"c.innerHTML={inner};}})();")


def on_will_set_content(web_content, context):
    screen = _screen_for(context)
    if not screen:
        return
    web = getattr(context, "web", None) or (mw.toolbarWeb if screen == "top" else mw.bottomWeb if screen == "bottom" else mw.web)
    web_content.head += f"<style id='{STYLE_ID}'>{css_for(screen)}</style><style>{_vars_css(web)}</style>"
    if screen == "main":
        web_content.body += f"<div id='ast-credit'>{credit_html(current_wallpaper())}</div>"
    custom = _custom_css(screen).strip()
    if custom:
        web_content.head += f"<style>{custom}</style>"


def on_style_injected(web):
    """The congrats screen is a separate page; give it the wallpaper too."""
    page = os.path.basename(web.page().url().path())
    if page in ("congrats.html", "congrats"):
        web.eval(_set_style_js(css_for("main")))


def replace_gear(deck_browser, content):
    gear = current_gear()
    if gear:
        content.tree = content.tree.replace(
            "<img src='/_anki/imgs/gears.svg'", f"<img src='{_url('gear', gear)}'")


# ---------------------------------------------------------------- live updates

def _set_style_js(css, preload=None):
    body = (f"var s=document.getElementById({json.dumps(STYLE_ID)});"
            f"if(!s){{s=document.createElement('style');s.id={json.dumps(STYLE_ID)};document.head.appendChild(s);}}"
            f"s.textContent={json.dumps(css)};")
    if preload:
        # load the picture first so the swap is a smooth fade, never a blank flash
        return (f"(function(){{var i=new Image();var go=function(){{{body}}};"
                f"i.onload=go;i.onerror=go;i.src={json.dumps(preload)};}})();")
    return f"(function(){{{body}}})();"


def apply_live(cfg=None):
    """Re-style every open screen in place, without reloading anything."""
    name = current_wallpaper(cfg)
    preload = picture_url(name) if name else None
    main = {"review": "review", "deckBrowser": "main", "overview": "main"}.get(mw.state)
    targets = []
    if main:
        targets.append((mw.web, main))
    if getattr(mw, "toolbarWeb", None):
        targets.append((mw.toolbarWeb, "top"))
    if getattr(mw, "bottomWeb", None):
        targets.append((mw.bottomWeb, "bottom"))
    for web, screen in targets:
        try:
            web.eval(_set_style_js(css_for(screen, cfg), preload))
            if screen == "main":
                web.eval(_credit_js(name))
        except Exception:
            pass
    sync_geometry()


def on_state_change(new_state, old_state):
    # bars switch between deck-screen and review brightness with the main screen
    if new_state in ("review", "overview", "deckBrowser") and old_state != new_state:
        QTimer.singleShot(0, lambda: apply_live())
    if new_state == "deckBrowser" and old_state not in ("deckBrowser", "startup", "profileManager"):
        if get_config().get("New wallpaper on each visit to the deck list"):
            next_wallpaper()


def on_js_message(handled, message, context):
    if message == "ast:new-wallpaper":
        next_wallpaper()
        return (True, None)
    if isinstance(message, str) and message.startswith("ast:open:https://"):
        from aqt.utils import openLink
        openLink(message[len("ast:open:"):])
        return (True, None)
    return handled


def add_deck_list_button():
    """A quiet 'New wallpaper' button next to Create Deck / Import File."""
    link = ["", "ast:new-wallpaper", "New wallpaper"]
    if link not in DeckBrowser.drawLinks:
        DeckBrowser.drawLinks.append(link)


def on_config_saved(cfg):
    apply_live()


def ensure_folders():
    import shutil
    for folder in (BG_DIR, GEAR_DIR, CSS_DIR):
        os.makedirs(folder, exist_ok=True)
    # first run: start with the built-in wallpapers
    defaults = os.path.join(USER_FILES, "default_wallpapers")
    marker = os.path.join(USER_FILES, ".default_wallpapers_copied")
    if os.path.isdir(defaults) and not os.path.exists(marker):
        for name in _list(defaults):
            if not os.path.exists(os.path.join(BG_DIR, name)):
                shutil.copy2(os.path.join(defaults, name), os.path.join(BG_DIR, name))
        try:
            open(marker, "w").close()
        except OSError:
            pass
    # first run without the old add-on: start with the bundled gear icons
    default_gears = os.path.join(USER_FILES, "default_gear")
    if not gears() and os.path.isdir(default_gears):
        for name in _list(default_gears):
            shutil.copy2(os.path.join(default_gears, name), os.path.join(GEAR_DIR, name))


def open_settings():
    from .settings_window import open_settings as open_window
    open_window(0)


ensure_folders()
add_deck_list_button()
gui_hooks.webview_will_set_content.append(on_will_set_content)
gui_hooks.webview_did_inject_style_into_page.append(on_style_injected)
gui_hooks.deck_browser_will_render_content.append(replace_gear)
gui_hooks.state_did_change.append(on_state_change)
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.main_window_did_init.append(on_main_window_ready)
mw.addonManager.setConfigAction(ADDON, open_settings)
mw.addonManager.setConfigUpdatedAction(ADDON, on_config_saved)
# switching between light and dark mode changes the dimming color
gui_hooks.theme_did_change.append(lambda: QTimer.singleShot(0, apply_live))
