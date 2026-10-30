"""
One-time import from add-ons this package replaces:
  - Custom Background Image and Gear Icon (1210908941)
  - Wallpaper Fetcher, Frosted Glass + Feedback, Anime Study Theme
    (earlier private versions of this add-on)

Copies your pictures, settings and download history over, then turns the
old add-ons off so nothing is drawn twice. Old folders are left in place
(only disabled), so you can delete them yourself from Tools → Add-ons.
Runs before the background code loads, so the copied pictures are found.
"""

import json
import os
import shutil
import traceback

from aqt import mw

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILES = os.path.join(ADDON_DIR, "user_files")
MARKER = os.path.join(USER_FILES, ".imported_old_addons.json")
LOG_PATH = os.path.join(USER_FILES, "migration_log.txt")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg")

KNOWN = {
    "background": {"dirs": {"1210908941"}, "names": ("custom background",)},
    "fetcher": {"dirs": {"anki_wallpaper_fetcher"}, "names": ("wallpaper fetcher",)},
    "glass": {"dirs": {"frosted_glass_feedback"}, "names": ("frosted glass",)},
    "theme": {"dirs": {"anime_study_theme"}, "names": ("anime study theme",)},
}

summary = []      # shown to the user once the main window is ready
disabled = []


def log(msg):
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg.rstrip() + "\n")
    except Exception:
        pass


def _addon_name(path):
    for fname in ("meta.json", "manifest.json"):
        try:
            with open(os.path.join(path, fname), encoding="utf-8") as f:
                name = json.load(f).get("name")
            if name:
                return str(name)
        except Exception:
            continue
    return ""


def find_old():
    """Return {kind: folder_name} for old add-ons found next to this one."""
    root = os.path.dirname(ADDON_DIR)
    ours = os.path.basename(ADDON_DIR)
    found = {}
    try:
        entries = sorted(os.listdir(root))
    except Exception:
        return found
    for entry in entries:
        path = os.path.join(root, entry)
        if entry == ours or not os.path.isdir(path):
            continue
        name = _addon_name(path).lower()
        for kind, rule in KNOWN.items():
            if kind in found:
                continue
            if entry in rule["dirs"] or any(n in name for n in rule["names"]):
                found[kind] = entry
    return found


def _copy_tree_files(src, dst, exts=None):
    """Copy files that don't already exist at the destination. Returns count."""
    if not os.path.isdir(src):
        return 0
    os.makedirs(dst, exist_ok=True)
    n = 0
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if not os.path.isfile(s) or name.endswith(".part"):
            continue
        if exts and not name.lower().endswith(exts):
            continue
        if os.path.exists(d):
            continue
        shutil.copy2(s, d)  # copy2 keeps timestamps, so wallpaper pruning ages stay right
        n += 1
    return n


def import_background(old_dir, module):
    old = os.path.join(os.path.dirname(ADDON_DIR), old_dir)
    pics = _copy_tree_files(os.path.join(old, "user_files", "background"),
                            os.path.join(USER_FILES, "background"), IMAGE_EXT)
    _copy_tree_files(os.path.join(old, "user_files", "gear"),
                     os.path.join(USER_FILES, "gear"), IMAGE_EXT)
    # custom CSS files: keep the user's edits if they made any
    old_css = os.path.join(old, "user_files", "css")
    new_css = os.path.join(USER_FILES, "css")
    if os.path.isdir(old_css):
        os.makedirs(new_css, exist_ok=True)
        for name in os.listdir(old_css):
            if name.endswith(".css"):
                shutil.copy2(os.path.join(old_css, name), os.path.join(new_css, name))
    old_cfg = mw.addonManager.getConfig(old_dir)
    if isinstance(old_cfg, dict) and old_cfg:
        cfg = mw.addonManager.getConfig(module) or {}
        cfg.update(old_cfg)
        mw.addonManager.writeConfig(module, cfg)
    summary.append(f"background settings and {pics} picture(s)")


def import_fetcher(old_dir):
    from .wallpaper_fetcher import import_settings
    old = os.path.join(os.path.dirname(ADDON_DIR), old_dir)
    import_settings(mw.addonManager.getConfig(old_dir) or {},
                    os.path.join(old, "user_files", "state.json"))
    summary.append("wallpaper fetcher settings and history")


def import_glass(old_dir):
    from .frosted_glass import import_settings, USER_SOUND_DIR
    import_settings(mw.addonManager.getConfig(old_dir) or {})
    old = os.path.join(os.path.dirname(ADDON_DIR), old_dir)
    _copy_tree_files(os.path.join(old, "user_files", "sounds"), USER_SOUND_DIR, (".wav",))
    summary.append("glass & sound settings")


def import_theme(old_dir, module):
    """The earlier private build of this add-on: same folder layout."""
    old = os.path.join(os.path.dirname(ADDON_DIR), old_dir, "user_files")
    pics = 0
    src = os.path.join(old, "background")
    if os.path.isdir(src):
        dst = os.path.join(USER_FILES, "background")
        os.makedirs(dst, exist_ok=True)
        for name in os.listdir(src):
            s, d = os.path.join(src, name), os.path.join(dst, name)
            if (os.path.isfile(s) and name.lower().endswith(IMAGE_EXT) and not name.startswith("auto_nsfw_")
                    and not os.path.exists(d)):
                shutil.copy2(s, d)
                pics += 1
    _copy_tree_files(os.path.join(old, "gear"), os.path.join(USER_FILES, "gear"), IMAGE_EXT)
    _copy_tree_files(os.path.join(old, "css"), os.path.join(USER_FILES, "css"), (".css",))
    _copy_tree_files(os.path.join(old, "glass_sounds"), os.path.join(USER_FILES, "glass_sounds"), (".wav",))
    for name in ("frosted_glass.json", "wallpaper_fetcher_state.json"):
        if os.path.isfile(os.path.join(old, name)) and not os.path.exists(os.path.join(USER_FILES, name)):
            shutil.copy2(os.path.join(old, name), os.path.join(USER_FILES, name))
    try:
        with open(os.path.join(old, "wallpaper_fetcher.json"), encoding="utf-8") as f:
            fetcher = json.load(f)
        from .wallpaper_fetcher import import_settings
        fetcher["style"] = "anime"  # it only ever fetched anime art
        import_settings(fetcher, None)
    except Exception:
        pass
    old_cfg = mw.addonManager.getConfig(old_dir)
    if isinstance(old_cfg, dict) and old_cfg:
        cfg = mw.addonManager.getConfig(module) or {}
        cfg.update(old_cfg)
        mw.addonManager.writeConfig(module, cfg)
    summary.append(f"your settings and {pics} picture(s) from Anime Study Theme")


def run(module):
    if os.path.exists(MARKER):
        return
    found = find_old()
    steps = {"background": lambda d: import_background(d, module),
             "fetcher": import_fetcher,
             "glass": import_glass,
             "theme": lambda d: import_theme(d, module)}
    for kind, old_dir in found.items():
        try:
            steps[kind](old_dir)
        except Exception:
            log(f"importing {kind} from {old_dir} failed:\n" + traceback.format_exc())
        try:
            if mw.addonManager.isEnabled(old_dir):
                mw.addonManager.toggleEnabled(old_dir, enable=False)
                disabled.append(_addon_name(os.path.join(os.path.dirname(ADDON_DIR), old_dir)) or old_dir)
        except Exception:
            log(f"could not disable {old_dir}:\n" + traceback.format_exc())
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        with open(MARKER, "w", encoding="utf-8") as f:
            json.dump({"found": found, "imported": summary, "disabled": disabled}, f, indent=2)
    except Exception:
        log("could not write marker:\n" + traceback.format_exc())


def message():
    """A short note for the user after the first launch, or None."""
    if not summary and not disabled:
        return None
    parts = []
    if summary:
        parts.append("Imported " + ", ".join(summary) + ".")
    if disabled:
        parts.append("Turned off the old add-ons (" + ", ".join(disabled) +
                     "). Restart Anki once so they stop loading.")
    return "Frosted Glass: " + " ".join(parts)
