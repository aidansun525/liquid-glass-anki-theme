"""
Wallpaper downloads (part of Frosted Glass: Anki Aesthetic Overhaul)
------------------------------------------------
Each day, fetches a few new wallpapers in one of two styles:

  professional  photos from Wallhaven's "General" category on the topics you pick
  anime         safe-rated anime art from Konachan and/or Wallhaven

Runs in a background thread when a profile opens, so it never delays startup
or blocks reviewing. Uses only the Python standard library.
Settings live in user_files/wallpaper_fetcher.json.

"""

import json
import os
import random
import re
import string
import threading
import time
import urllib.parse
import urllib.request
from datetime import date

from aqt import gui_hooks, mw
from aqt.qt import QAction
from aqt.utils import openFolder, tooltip

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.dirname(MODULE_DIR)  # the add-on's folder
USER_FILES = os.path.join(ADDON_DIR, "user_files")
BACKGROUND_DIR = os.path.join(USER_FILES, "background")
CONFIG_PATH = os.path.join(USER_FILES, "wallpaper_fetcher.json")
STATE_PATH = os.path.join(USER_FILES, "wallpaper_fetcher_state.json")
LOG_PATH = os.path.join(USER_FILES, "wallpaper_fetcher_log.txt")

# Every file this add-on downloads starts with this prefix. Nothing without
# the prefix is ever touched, so your own pictures in the folder are safe.
PREFIX = "auto_"
PRO_PREFIX = PREFIX + "pro_"
ANIME_PREFIXES = (PREFIX + "konachan_", PREFIX + "wallhaven_")

USER_AGENT = "FrostedGlassAnkiTheme/1.0 (+https://github.com/aidansun525/liquid-glass-anki-theme)"
OK_EXTENSIONS = (".jpg", ".jpeg", ".png")

# Topic shown in Settings -> Wallhaven search (empty = anything)
TOPICS = {
    "Nature": "nature",
    "Architecture": "architecture",
    "Landscape": "landscape",
}

DEFAULTS = {
    "style": "professional",
    "topics": list(TOPICS),
    "custom_tags": "",
    "images_per_day": 3,
    "use_konachan": True,
    "use_wallhaven": True,
    "min_width": 1920,
    "min_height": 1080,
    "konachan_tags": "",
    "wallhaven_query": "",
    "wallhaven_categories": "010",
    "wallhaven_ratios": "16x9",
    "delete_after_days": 3,
    "always_keep_newest": 5,
    "max_images_kept": 0,
    "timeout_seconds": 25,
    "show_notification": False,
}


def style(cfg=None):
    return "anime" if (cfg or get_config()).get("style") == "anime" else "professional"


def is_style_download(name, which):
    """Is this downloaded file part of the given style's pictures?"""
    if which == "anime":
        return name.startswith(ANIME_PREFIXES)
    return name.startswith(PRO_PREFIX)


def chosen_topics(cfg):
    return [t for t in (cfg.get("topics") or []) if t in TOPICS]


def searches(cfg):
    """What Professional mode searches for: the ticked topics plus your own
    tags, if you typed any. Each download picks one at random."""
    pool = [TOPICS[t] for t in chosen_topics(cfg)]
    custom = str(cfg.get("custom_tags") or "").strip()
    if custom:
        pool.append(custom)
    return pool or list(TOPICS.values())


# called on the main thread after new pictures were saved
on_fetched = []


# ---------------------------------------------------------------- utilities

def log(message):
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {message}\n")
    except Exception:
        pass


def write_config(cfg):
    os.makedirs(USER_FILES, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({k: cfg[k] for k in DEFAULTS if k in cfg}, fh, indent=4)
    os.replace(tmp, CONFIG_PATH)


def get_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            cfg.update({k: v for k, v in saved.items() if v is not None and k in DEFAULTS})
    except FileNotFoundError:
        try:
            write_config(cfg)  # create it so there's a file to edit
        except Exception:
            pass
    except Exception as exc:
        log(f"could not read config, using defaults: {exc}")
    return cfg


def import_settings(old_cfg, old_state_path):
    """Bring over settings and download history from the standalone add-on.
    The old 'folder' setting is dropped: pictures now go into this add-on."""
    if not os.path.exists(CONFIG_PATH) and isinstance(old_cfg, dict):
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in old_cfg.items() if k in DEFAULTS and v is not None})
        write_config(merged)
    if old_state_path and os.path.isfile(old_state_path) and not os.path.exists(STATE_PATH):
        with open(old_state_path, encoding="utf-8") as src, open(STATE_PATH, "w", encoding="utf-8") as dst:
            dst.write(src.read())


def target_folder():
    os.makedirs(BACKGROUND_DIR, exist_ok=True)
    return BACKGROUND_DIR


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except Exception:
        state = {}
    state.setdefault("last_date", "")
    state.setdefault("count_today", 0)
    state.setdefault("seen", {})
    state["seen"].setdefault("konachan", [])
    state["seen"].setdefault("wallhaven", [])
    return state


def save_state(state):
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        # Keep the "already downloaded" lists from growing forever.
        for key in state.get("seen", {}):
            state["seen"][key] = state["seen"][key][-4000:]
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception as exc:
        log(f"could not save state: {exc}")


def http_get(url, timeout, as_json=False, headers=None):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json" if as_json else "image/*",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    if as_json:
        return json.loads(payload.decode("utf-8", "replace"))
    return payload


def absolute(url):
    if url.startswith("//"):
        return "https:" + url
    return url


def extension_of(url, fallback=".jpg"):
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return ext if ext in OK_EXTENSIONS else fallback


# ----------------------------------------------------------------- sources

def konachan_candidates(cfg):
    """konachan.net is Konachan's safe-only mirror; ratings are checked again below."""
    tags = "order:random rating:safe"
    extra = str(cfg.get("konachan_tags") or "").strip()
    if extra:
        tags += " " + extra
    url = "https://konachan.net/post.json?" + urllib.parse.urlencode({"tags": tags, "limit": 60})
    posts = http_get(url, cfg["timeout_seconds"], as_json=True)

    results = []
    for post in posts:
        if post.get("rating") != "s":
            continue
        file_url = absolute(post.get("file_url") or "")
        if not file_url or extension_of(file_url, "") not in OK_EXTENSIONS:
            continue
        if int(post.get("width") or 0) < cfg["min_width"]:
            continue
        if int(post.get("height") or 0) < cfg["min_height"]:
            continue
        results.append({"source": "konachan", "id": str(post.get("id")), "url": file_url})
    return results


def wallhaven_candidates(cfg):
    """Wallhaven's 'sfw' purity level only. Anime style searches the Anime
    category; Professional searches the General category (no anime, no people)."""
    pro = style(cfg) == "professional"
    params = {
        "purity": "100",
        "categories": "100" if pro else str(cfg.get("wallhaven_categories") or "010"),
        "sorting": "random",
        "atleast": f"{cfg['min_width']}x{cfg['min_height']}",
        "seed": "".join(random.choices(string.ascii_lowercase + string.digits, k=6)),
    }
    if str(cfg.get("wallhaven_ratios") or "").strip():
        params["ratios"] = cfg["wallhaven_ratios"].strip()
    if pro:
        params["q"] = random.choice(searches(cfg))
    elif str(cfg.get("wallhaven_query") or "").strip():
        params["q"] = cfg["wallhaven_query"].strip()

    url = "https://wallhaven.cc/api/v1/search?" + urllib.parse.urlencode(params)
    payload = http_get(url, cfg["timeout_seconds"], as_json=True)

    results = []
    for item in payload.get("data", []):
        if item.get("purity") != "sfw":
            continue
        path = item.get("path") or ""
        if extension_of(path, "") not in OK_EXTENSIONS:
            continue
        if pro and item.get("category") not in (None, "general"):
            continue
        results.append({"source": "wallhaven", "id": str(item.get("id")), "url": path, "pro": pro})
    return results


# ----------------------------------------------------------------- fetching

def download_one(cfg, folder, state):
    """Grab one unseen wallpaper in the current style. Returns the filename, or None."""
    if style(cfg) == "anime":
        providers = []
        if cfg.get("use_konachan"):
            providers.append(konachan_candidates)
        if cfg.get("use_wallhaven"):
            providers.append(wallhaven_candidates)
    else:
        providers = [wallhaven_candidates]
    if not providers:
        log("no sources enabled in config")
        return None

    random.shuffle(providers)

    for provider in providers:
        try:
            candidates = provider(cfg)
        except Exception as exc:
            log(f"{provider.__name__} failed: {exc}")
            continue

        fresh = [
            c for c in candidates if c["id"] not in state["seen"].get(c["source"], [])
        ]
        random.shuffle(fresh)

        for candidate in fresh[:5]:
            seen = state["seen"].setdefault(candidate["source"], [])
            safe_id = re.sub(r"[^A-Za-z0-9_-]", "", candidate["id"])
            prefix = PRO_PREFIX if candidate.get("pro") else PREFIX
            name = f"{prefix}{candidate['source']}_{safe_id}{extension_of(candidate['url'])}"
            destination = os.path.join(folder, name)
            if os.path.exists(destination):
                seen.append(candidate["id"])
                continue
            try:
                data = http_get(candidate["url"], cfg["timeout_seconds"])
            except Exception as exc:
                log(f"download failed for {candidate['url']}: {exc}")
                continue
            if len(data) < 20_000:  # almost certainly an error page, not a wallpaper
                continue
            # Write to a temp name first so a half-finished file is never picked up.
            temp = destination + ".part"
            with open(temp, "wb") as fh:
                fh.write(data)
            os.replace(temp, destination)
            seen.append(candidate["id"])
            log(f"saved {name} ({len(data) // 1024} KB)")
            return name

    return None


def _remove(path):
    os.remove(path)


def prune(folder, cfg):
    """Delete auto-downloaded files older than delete_after_days.

    Only files starting with PREFIX are ever considered, so your own pictures
    in this folder are never touched. The newest few are always kept even if
    they are past the age limit, so a stretch of failed downloads can't leave
    the folder empty and the background blank.
    """
    max_age_days = float(cfg.get("delete_after_days") or 0)
    floor = int(cfg.get("always_keep_newest") or 0)
    hard_cap = int(cfg.get("max_images_kept") or 0)

    ours = []
    for entry in os.scandir(folder):
        if entry.is_file() and entry.name.startswith(PREFIX) and not entry.name.endswith(".part"):
            ours.append((entry.stat().st_mtime, entry.path))
    if not ours:
        return

    ours.sort(reverse=True)  # newest first
    protected = {path for _, path in ours[:floor]} if floor > 0 else set()

    if max_age_days > 0:
        cutoff = time.time() - max_age_days * 86400
        for mtime, path in ours:
            if mtime < cutoff and path not in protected:
                try:
                    _remove(path)
                    age = (time.time() - mtime) / 86400
                    log(f"pruned {os.path.basename(path)} ({age:.1f} days old)")
                except Exception as exc:
                    log(f"could not prune {path}: {exc}")

    # Optional extra safety net: cap the total number of downloaded files.
    if hard_cap > 0:
        remaining = sorted(
            (m, p) for m, p in ours if os.path.exists(p)
        )  # oldest first
        for _, path in remaining[: max(0, len(remaining) - hard_cap)]:
            try:
                _remove(path)
                log(f"pruned {os.path.basename(path)} (over the {hard_cap} file cap)")
            except Exception as exc:
                log(f"could not prune {path}: {exc}")


def worker(force=False):
    try:
        cfg = get_config()
        folder = target_folder()
        state = load_state()

        today = date.today().isoformat()
        if state["last_date"] != today:
            state["last_date"] = today
            state["count_today"] = 0

        quota = int(cfg.get("images_per_day") or 0)
        wanted = quota if force else max(0, quota - int(state["count_today"]))
        if wanted <= 0:
            log("daily quota already met, nothing to do")
            return

        saved = 0
        for _ in range(wanted):
            name = download_one(cfg, folder, state)
            if not name:
                break
            saved += 1
            if not force:
                state["count_today"] += 1
            time.sleep(2)  # be polite to both sites

        prune(folder, cfg)
        save_state(state)

        if saved:
            mw.taskman.run_on_main(lambda: [fn() for fn in list(on_fetched)])
        if saved and (force or cfg.get("show_notification")):
            mw.taskman.run_on_main(
                lambda: tooltip(f"{saved} new wallpaper(s)")
            )
        log(f"run finished, {saved} new file(s) in {folder}")
    except Exception as exc:
        log(f"unexpected error: {exc}")


def start(force=False):
    threading.Thread(target=worker, kwargs={"force": force}, daemon=True).start()


# -------------------------------------------------------------- Anki wiring

def on_profile_open():
    start(force=False)


def fetch_now():
    tooltip("Getting new wallpapers in the background…")
    start(force=True)


def open_folder():
    openFolder(target_folder())


def add_menu_items(menu):
    action = QAction("Fetch wallpapers now", mw)
    action.triggered.connect(fetch_now)
    menu.addAction(action)


gui_hooks.profile_did_open.append(on_profile_open)
