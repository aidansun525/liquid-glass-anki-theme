"""
Frosted Glass + Feedback (part of Frosted Glass)
----------------------------------------------------
1. Turns the card area in the reviewer into a frosted-glass panel, so your
   background wallpaper shows through, blurred, behind the card text.
2. Quiet feedback the instant you answer: a soft colored glow along the
   panel's edge and a gentle piano note.

The wallpaper is drawn by the bundled Custom Background code in the parent
package. Settings live in user_files/frosted_glass.json so they never clash
with the background settings.
"""

import json
import os
import re
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QAction, QApplication, QUrl
from aqt.reviewer import Reviewer, ReviewerBottomBar
from aqt.utils import openFolder, tooltip

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(MODULE_DIR)          # the combined add-on's folder
ADDON_FOLDER = os.path.basename(ADDON_DIR)
WEB_DIR = os.path.join(MODULE_DIR, "web")
SOUND_DIR = os.path.join(ADDON_DIR, "web", "glass_sounds")
USER_SOUND_DIR = os.path.join(ADDON_DIR, "user_files", "glass_sounds")
CONFIG_PATH = os.path.join(ADDON_DIR, "user_files", "frosted_glass.json")
LOG_PATH = os.path.join(ADDON_DIR, "user_files", "frosted_glass_log.txt")

KEYS = ("again", "hard", "good", "easy")
EASE_TO_KEY = {1: "again", 2: "hard", 3: "good", 4: "easy"}
CONFIG_VERSION = 3

DEFAULTS = {
    "config_version": CONFIG_VERSION,
    "glass_enabled": True,
    "visual_feedback_enabled": True,
    "sound_enabled": True,
    "sound_volume": 0.3,
    "blur_px": 22,
    "glass_strength": 0.4,
    "panel_max_width_px": 860,
    "panel_min_height_px": 360,
    "card_font_px": 0,
    "corner_radius_px": 18,
    "colors": {"again": "#ff7a8a", "hard": "#ffc56b", "good": "#7fe0a8", "easy": "#8cc8ff"},
}

OBSOLETE_KEYS = ("labels", "badge", "badge_position", "vignette", "sparkles")


# ---------------------------------------------------------------- helpers

def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _read_user_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_config():
    cfg = dict(DEFAULTS)
    user = _read_user_config()
    cfg.update({k: v for k, v in user.items() if k not in OBSOLETE_KEYS})
    colors = dict(DEFAULTS["colors"])
    colors.update(user.get("colors") or {})
    cfg["colors"] = colors
    return cfg


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in cfg.items() if k not in OBSOLETE_KEYS}, f, indent=4)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        log("could not save config:\n" + traceback.format_exc())


def import_settings(old):
    """Bring over settings from the standalone Frosted Glass add-on (v1.2 keys only)."""
    if os.path.exists(CONFIG_PATH) or not isinstance(old, dict):
        return
    if old.get("config_version", 1) < 2:
        return  # v1 values were tuned for a different look
    save_config({k: v for k, v in old.items() if k in DEFAULTS})


def _num(value, default, lo, hi):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _color(value, default):
    value = str(value or "").strip()
    return value if re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", value) else default


def sound_path(key):
    for folder in (USER_SOUND_DIR, SOUND_DIR):
        path = os.path.join(folder, f"{key}.wav")
        if os.path.isfile(path):
            return path
    return None


def sound_url(key):
    path = sound_path(key)
    if not path:
        return None
    rel = os.path.relpath(path, ADDON_DIR).replace(os.sep, "/")
    return f"/_addons/{ADDON_FOLDER}/{rel}?v={int(os.path.getmtime(path))}"


def answer_keys():
    """Your answer shortcuts (1-4 unless changed in Preferences) -> ease."""
    keys = {}
    try:
        for ease in (1, 2, 3, 4):
            key = mw.pm.get_answer_key(ease)
            if key:
                keys[str(key).lower()] = ease
    except Exception:
        keys = {"1": 1, "2": 2, "3": 3, "4": 4}
    return keys


def page_config(cfg):
    """The subset of config the reviewer page needs, already sanitized."""
    strength = _num(cfg.get("glass_strength"), 0.4, 0.0, 1.0)
    return {
        "glass": bool(cfg.get("glass_enabled", True)),
        "volume": _num(cfg.get("sound_volume"), 0.3, 0.0, 1.0),
        "colors": {k: _color(cfg["colors"].get(k), DEFAULTS["colors"][k]) for k in KEYS},
        "sounds": {k: u for k in KEYS if (u := sound_url(k))},
        "text_px": int(_num(cfg.get("card_font_px"), 0, 0, 96)),
        "glow_on": bool(cfg.get("visual_feedback_enabled", True)),
        "sound_on": bool(cfg.get("sound_enabled", True)),
        "answer_keys": answer_keys(),
        "vars": {
            "--fg-blur": f"{_num(cfg.get('blur_px'), 22, 0, 60):g}px",
            "--fg-width": f"{_num(cfg.get('panel_max_width_px'), 860, 300, 4000):g}px",
            "--fg-height": f"{_num(cfg.get('panel_min_height_px'), 360, 0, 2000):g}px",
            "--fg-radius": f"{_num(cfg.get('corner_radius_px'), 18, 0, 60):g}px",
            "--fg-tint-light": f"rgba(255, 255, 255, {strength:.2f})",
            "--fg-tint-dark": f"rgba(16, 17, 22, {min(1.0, strength + 0.02):.2f})",
        },
    }


def read_web(name):
    with open(os.path.join(WEB_DIR, name), encoding="utf-8") as f:
        return f.read()


def reviewer_web():
    if mw.state == "review" and getattr(mw, "reviewer", None) and mw.reviewer.web:
        return mw.reviewer.web
    return None


# ---------------------------------------------------------------- reviewer page

BOTTOM_JS = """
(function () {
  // Answer buttons: start the note as the button goes down, not on release.
  function press(ease) { if (window.pycmd) pycmd("fgpress:" + ease); }
  document.addEventListener("pointerdown", function (e) {
    var b = e.target.closest && e.target.closest("button[data-ease]");
    if (b && e.button === 0) press(b.getAttribute("data-ease"));
  }, true);
})();
"""


def inject(web_content, context):
    if isinstance(context, ReviewerBottomBar):
        web_content.head += f"<script>{BOTTOM_JS}</script>"
        return
    if not isinstance(context, Reviewer):
        return
    try:
        # let the page's own audio start without waiting for a click
        try:
            context.web.setPlaybackRequiresGesture(False)
        except Exception:
            pass
        conf_json = json.dumps(page_config(get_config())).replace("</", "<\\/")
        web_content.head += (
            f"<style id='fg-glass-css'>{read_web('glass.css')}</style>"
            "<style id='fg-text-size'></style>"
            f"<script>window.FG_CONFIG = {conf_json};</script>"
            f"<script>{read_web('feedback.js')}</script>"
        )
    except Exception:
        log("inject failed:\n" + traceback.format_exc())


def push_config_to_reviewer():
    """Apply config changes to an open review screen without reloading it."""
    web = reviewer_web()
    if web:
        conf_json = json.dumps(page_config(get_config()))
        web.eval(f"window.fgApply && window.fgApply({conf_json});")


# ---------------------------------------------------------------- native sound fallback
# Used only if the review page can't play audio itself, and for previews.

_effects = {}
_next = {}
_sound_ok = None


def load_sounds():
    global _sound_ok
    _effects.clear()
    try:
        from PyQt6.QtMultimedia import QSoundEffect
    except Exception:
        _sound_ok = False
        log("QtMultimedia not available.\n" + traceback.format_exc())
        return
    volume = _num(get_config().get("sound_volume"), 0.3, 0.0, 1.0)
    for key in KEYS:
        path = sound_path(key)
        if not path:
            continue
        players = []
        for _ in range(2):
            effect = QSoundEffect(mw)
            effect.setSource(QUrl.fromLocalFile(path))
            effect.setVolume(volume)
            players.append(effect)
        _effects[key] = players
        _next[key] = 0
    _sound_ok = True


def set_native_volume(volume):
    for players in _effects.values():
        for effect in players:
            effect.setVolume(volume)


def play_native(key):
    if _sound_ok is None:
        load_sounds()
    players = _effects.get(key)
    if not players:
        return
    try:
        i = _next[key]
        _next[key] = (i + 1) % len(players)
        players[i].play()
    except Exception:
        log("play failed:\n" + traceback.format_exc())


def press(ease):
    """An answer button went down: play the feedback now, in the review page."""
    web = reviewer_web()
    if web and ease in "1234":
        web.eval(f"window.fgPress && window.fgPress({int(ease)});")


def on_js_message(handled, message, context):
    if isinstance(message, str) and message.startswith("fgpress:"):
        press(message.split(":", 1)[1])
        return (True, None)
    if isinstance(message, str) and message.startswith("fgsound:"):
        key = message.split(":", 1)[1]
        if key in KEYS:
            play_native(key)
        return (True, None)
    return handled


# ---------------------------------------------------------------- answer hook

def on_will_answer(ease_tuple, reviewer, card):
    """Runs the moment you press an answer button, before Anki saves the
    answer, so the glow and note line up with your click."""
    proceed, ease = ease_tuple
    if proceed:
        cfg = get_config()
        glow = bool(cfg.get("visual_feedback_enabled", True))
        sound = bool(cfg.get("sound_enabled", True))
        if glow or sound:
            try:
                reviewer.web.eval(
                    f"window.fgFeedback && window.fgFeedback({int(ease)}, {str(glow).lower()}, {str(sound).lower()});"
                )
            except Exception:
                log("feedback failed:\n" + traceback.format_exc())
    return ease_tuple


# ---------------------------------------------------------------- settings window

# ---------------------------------------------------------------- Tools menu

_actions = {}


def toggle(option):
    cfg = get_config()
    cfg[option] = not cfg.get(option, True)
    save_config(cfg)
    sync_menu()
    push_config_to_reviewer()


def sync_menu(cfg=None):
    cfg = cfg or get_config()
    for option, action in _actions.items():
        action.setChecked(bool(cfg.get(option, True)))


def copy_diagnostics():
    web = reviewer_web()
    if not web:
        tooltip("Start reviewing a deck first, then run this again.")
        return

    def done(result):
        try:
            from anki.buildinfo import version as anki_version
        except Exception:
            anki_version = "unknown"
        text = f"Frosted Glass diagnostics\nAnki {anki_version}\nconfig: {json.dumps(page_config(get_config()))}\npage: {result}"
        QApplication.clipboard().setText(text)
        tooltip("Diagnostics copied. Paste them to Claude.")

    web.evalWithCallback("window.fgDiagnostics ? fgDiagnostics() : 'add-on script not loaded on this page'", done)


def open_sound_folder():
    os.makedirs(USER_SOUND_DIR, exist_ok=True)
    openFolder(USER_SOUND_DIR)


def add_menu_items(menu):
    """Quick on/off switches; everything else is in the Settings window."""
    for option, label in (
        ("glass_enabled", "Glass card panel"),
        ("visual_feedback_enabled", "Glow on answer"),
        ("sound_enabled", "Piano note on answer"),
    ):
        action = QAction(label, mw)
        action.setCheckable(True)
        action.triggered.connect(lambda _checked=False, o=option: toggle(o))
        menu.addAction(action)
        _actions[option] = action
    sync_menu()


def _side(answer_shown):
    web = reviewer_web()
    if web:
        web.eval(f"window.fgSide && window.fgSide({str(answer_shown).lower()});")


def on_profile_open():
    load_sounds()
    sync_menu()


gui_hooks.webview_will_set_content.append(inject)
gui_hooks.reviewer_will_answer_card.append(on_will_answer)
gui_hooks.reviewer_did_show_question.append(lambda card: _side(False))
gui_hooks.reviewer_did_show_answer.append(lambda card: _side(True))
gui_hooks.webview_did_receive_js_message.append(on_js_message)
gui_hooks.profile_did_open.append(on_profile_open)
