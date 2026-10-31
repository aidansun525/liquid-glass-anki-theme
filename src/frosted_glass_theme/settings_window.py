"""
One Settings window for the whole theme, with three tabs:
Wallpaper, Daily downloads, Glass & sound.

Everything applies live and saves by itself; there is no Save button.
"""

import json
import os
import shutil

from aqt import mw
from aqt.qt import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                    QGridLayout, QGroupBox, QHBoxLayout, QIcon, QImageReader, QLabel, QLineEdit,
                    QListView, QListWidget, QListWidgetItem, QPixmap, QPushButton, QRadioButton, QSize, QSlider,
                    QSpinBox, Qt, QTabWidget, QTimer, QVBoxLayout, QWidget)
from aqt.utils import getFile, openFolder, tooltip

from . import background as bg
from . import frosted_glass as fg
from . import wallpaper_fetcher as wf

THUMB = QSize(144, 81)
FITS = (("Fill the window", "cover"), ("Show the whole picture", "contain"), ("Original size", "auto"))
POSITIONS = (("Centre", "center"), ("Top", "top"), ("Bottom", "bottom"), ("Left", "left"), ("Right", "right"))


def _hint(text):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray; font-size: 11px;")
    return label


def _slider(lo, hi, value, suffix, on_change, zero_text=None):
    """A slider with its value shown on the right. Returns (layout, slider)."""
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(lo, hi)
    slider.setValue(int(value))
    def text(v):
        return zero_text if (zero_text and v == lo) else f"{v}{suffix}"

    label = QLabel(text(slider.value()))
    label.setMinimumWidth(52)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def changed(v):
        label.setText(text(v))
        on_change(v)

    slider.valueChanged.connect(changed)
    row = QHBoxLayout()
    row.addWidget(slider, 1)
    row.addWidget(label)
    return row, slider


def _thumbnail(path):
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and size.width() > 0:
        reader.setScaledSize(size.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
    image = reader.read()
    if image.isNull():
        return QIcon()
    pix = QPixmap.fromImage(image)
    x = max(0, (pix.width() - THUMB.width()) // 2)
    y = max(0, (pix.height() - THUMB.height()) // 2)
    return QIcon(pix.copy(x, y, THUMB.width(), THUMB.height()))


# ---------------------------------------------------------------- Wallpaper tab

class WallpaperTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = bg.get_config()
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.timeout.connect(lambda: bg.save_config(self.cfg))
        layout = QVBoxLayout(self)

        # picture gallery
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListView.ViewMode.IconMode)
        self.gallery.setIconSize(THUMB)
        self.gallery.setGridSize(QSize(THUMB.width() + 16, THUMB.height() + 30))
        self.gallery.setResizeMode(QListView.ResizeMode.Adjust)
        self.gallery.setMovement(QListView.Movement.Static)
        self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.gallery.setWordWrap(True)
        self.gallery.setMinimumHeight(2 * (THUMB.height() + 30) + 8)
        self.gallery.itemClicked.connect(self._picked)
        layout.addWidget(QLabel("Click a picture to use it, or choose <b>Shuffle</b> to rotate through all of them."))
        layout.addWidget(_hint("Want one wallpaper that never changes? Click it here, and set New pictures per day "
                               "to Off on the Daily downloads tab."))
        layout.addWidget(self.gallery, 1)

        buttons = QHBoxLayout()
        for label, fn, tip in (
            ("New wallpaper", self._new, "Show a different random picture now (Ctrl+Shift+W)"),
            ("Add pictures…", self._add, "Copy pictures from your computer into the wallpaper folder"),
            ("Open folder", lambda: openFolder(bg.BG_DIR), "Add or delete pictures yourself"),
        ):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.rotate = QCheckBox("Change the picture each time I go back to the deck list")
        self.rotate.setChecked(bool(self.cfg.get("New wallpaper on each visit to the deck list")))
        self.rotate.toggled.connect(lambda on: self._set("New wallpaper on each visit to the deck list", bool(on)))
        layout.addWidget(self.rotate)

        look = QGroupBox("Look")
        form = QFormLayout(look)
        self.sliders = {}
        for key, label, lo, hi in (
            ("background opacity main", "Brightness on deck screens", 10, 100),
            ("background opacity review", "Brightness while reviewing", 10, 100),
            ("background scale", "Zoom", 100, 200),
        ):
            row, slider = _slider(lo, hi, round(bg._num(self.cfg[key], 1, 0, 3) * 100), "%",
                                  lambda v, k=key: self._set(k, f"{v / 100:g}"))
            form.addRow(label, row)
            self.sliders[key] = slider
        self.fit = QComboBox()
        for text, value in FITS:
            self.fit.addItem(text, value)
        self.fit.setCurrentIndex(max(0, self.fit.findData(self.cfg["background-size"])))
        self.fit.currentIndexChanged.connect(lambda: self._set("background-size", self.fit.currentData()))
        form.addRow("Fit", self.fit)
        self.position = QComboBox()
        for text, value in POSITIONS:
            self.position.addItem(text, value)
        self.position.setCurrentIndex(max(0, self.position.findData(self.cfg["background-position"])))
        self.position.currentIndexChanged.connect(lambda: self._set("background-position", self.position.currentData()))
        form.addRow("Focus on", self.position)
        self.where = {}
        for key, label in (("Reviewer image", "Show it while reviewing"),
                           ("Toolbar image", "Show it behind the top and bottom bars")):
            box = QCheckBox(label)
            box.setChecked(bool(self.cfg.get(key)))
            box.toggled.connect(lambda on, k=key: self._set(k, bool(on)))
            form.addRow("", box)
            self.where[key] = box
        self.gear = QComboBox()
        self.gear.setIconSize(QSize(18, 18))
        self.gear.addItem("Anki's own", bg.ANKI_GEAR)
        self.gear.addItem("Shuffle", "random")
        for name in bg.gears():
            self.gear.addItem(QIcon(os.path.join(bg.GEAR_DIR, name)), os.path.splitext(name)[0], name)
        self.gear.setCurrentIndex(max(0, self.gear.findData(self.cfg["Image name for gear"])))
        self.gear.currentIndexChanged.connect(self._gear_changed)
        form.addRow("Deck gear icon", self.gear)
        layout.addWidget(look)
        self.fill_gallery()

    def fill_gallery(self):
        self.gallery.clear()
        shuffle = QListWidgetItem(QIcon(), "Shuffle")
        shuffle.setData(Qt.ItemDataRole.UserRole, "random")
        shuffle.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        shuffle.setSizeHint(QSize(THUMB.width() + 12, THUMB.height() + 26))
        self.gallery.addItem(shuffle)
        choice = self.cfg["Image name for background"]
        for name in bg.wallpapers():
            item = QListWidgetItem(_thumbnail(os.path.join(bg.BG_DIR, name)), "")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(name)
            self.gallery.addItem(item)
        for i in range(self.gallery.count()):
            item = self.gallery.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == (choice if choice in bg.wallpapers() else "random"):
                self.gallery.setCurrentItem(item)

    def _picked(self, item):
        name = item.data(Qt.ItemDataRole.UserRole)
        if name == "random":
            self._set("Image name for background", "random")
        else:
            self._set("Image name for background", name)

    def _new(self):
        bg.next_wallpaper()

    def follow_new_wallpaper(self):
        self.cfg["Image name for background"] = "random"
        self.gallery.setCurrentRow(0)

    def _add(self):
        def copy(paths):
            if isinstance(paths, str):
                paths = [paths]
            for path in paths or []:
                try:
                    shutil.copy2(path, os.path.join(bg.BG_DIR, os.path.basename(path)))
                except OSError:
                    pass
            self.fill_gallery()

        getFile(self, "Add pictures", cb=copy, filter="*.jpg *.jpeg *.png *.webp *.gif *.bmp", multi=True)

    def _gear_changed(self):
        self._set("Image name for gear", self.gear.currentData())
        bg.save_config(self.cfg)
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()

    def _set(self, key, value):
        self.cfg[key] = value
        bg.apply_live(self.cfg)
        self._save.start(300)

    def restore_defaults(self):
        for key, slider in self.sliders.items():
            slider.setValue(round(float(bg.DEFAULTS[key]) * 100))
        for key, box in self.where.items():
            box.setChecked(bg.DEFAULTS[key])
        self.rotate.setChecked(False)
        self.fit.setCurrentIndex(max(0, self.fit.findData(bg.DEFAULTS["background-size"])))
        self.position.setCurrentIndex(max(0, self.position.findData(bg.DEFAULTS["background-position"])))

    def flush(self):
        self._save.stop()
        bg.save_config(self.cfg)


# ---------------------------------------------------------------- Daily downloads tab

class DownloadsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = wf.get_config()
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.timeout.connect(self.flush)
        layout = QVBoxLayout(self)
        intro = QLabel("Each time you open Anki, a few new wallpapers are added in the background.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        warning = QLabel("All downloaded pictures come from the internet and MAY BE INAPPROPRIATE FOR "
                         "PROFESSIONAL SETTINGS. For the safest option, TURN OFF RANDOM WALLPAPERS: set "
                         "New pictures per day to Off and pick one of the built-in pictures on the Wallpaper tab.")
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #d32f2f; font-weight: bold;")
        self.warning = warning
        layout.addWidget(warning)

        form = QFormLayout()
        self.per_day = QSpinBox()
        self.per_day.setRange(0, 30)
        self.per_day.setValue(int(self.cfg["images_per_day"]))
        self.per_day.setSpecialValueText("Off")
        self.per_day.valueChanged.connect(lambda v: self._set("images_per_day", v))
        form.addRow("New pictures per day", self.per_day)

        self.professional = QRadioButton("Professional photos")
        self.anime = QRadioButton("Anime art")
        (self.anime if wf.style(self.cfg) == "anime" else self.professional).setChecked(True)
        self.professional.toggled.connect(lambda on: on and self._style("professional"))
        self.anime.toggled.connect(lambda on: on and self._style("anime"))
        kinds = QHBoxLayout()
        kinds.addWidget(self.professional)
        kinds.addWidget(self.anime)
        kinds.addStretch(1)
        form.addRow("Wallpaper style", kinds)
        layout.addLayout(form)

        # professional: Wallhaven General category, by topic
        self.pro_box = QGroupBox("Professional photos")
        pro = QFormLayout(self.pro_box)
        topics = QHBoxLayout()
        self.topics = {}
        chosen = wf.chosen_topics(self.cfg)
        for topic in wf.TOPICS:
            box = QCheckBox(topic)
            box.setChecked(topic in chosen)
            box.toggled.connect(lambda on, t=topic: self._topic(t, on))
            topics.addWidget(box)
            self.topics[topic] = box
        topics.addStretch(1)
        pro.addRow("Topics", topics)
        self.custom = QLineEdit(str(self.cfg.get("custom_tags") or ""))
        self.custom.setPlaceholderText("optional, e.g. ocean, autumn, snow")
        self.custom.setToolTip("Your own search, used alongside the ticked topics")
        self.custom.textChanged.connect(lambda t: self._set("custom_tags", t.strip(), delay=800))
        pro.addRow("Your own tags", self.custom)
        pro.addRow(_hint("Safe-rated photos from Wallhaven's General category (no anime, no people)."))
        layout.addWidget(self.pro_box)

        # anime: Konachan / Wallhaven, safe-rated only
        self.anime_box = QGroupBox("Anime art (safe-rated only)")
        an = QFormLayout(self.anime_box)
        self.konachan = QCheckBox("Konachan")
        self.konachan.setChecked(bool(self.cfg["use_konachan"]))
        self.konachan.toggled.connect(lambda on: self._set("use_konachan", bool(on)))
        self.wallhaven = QCheckBox("Wallhaven")
        self.wallhaven.setChecked(bool(self.cfg["use_wallhaven"]))
        self.wallhaven.toggled.connect(lambda on: self._set("use_wallhaven", bool(on)))
        sites = QHBoxLayout()
        sites.addWidget(self.konachan)
        sites.addWidget(self.wallhaven)
        sites.addStretch(1)
        an.addRow("From", sites)
        self.tags = QLineEdit(str(self.cfg.get("konachan_tags") or ""))
        self.tags.setPlaceholderText("anything, or e.g. scenery sky")
        self.tags.textChanged.connect(lambda t: self._set("konachan_tags", t.strip(), delay=800))
        an.addRow("Konachan tags", self.tags)
        self.query = QLineEdit(str(self.cfg.get("wallhaven_query") or ""))
        self.query.setPlaceholderText("anything, or e.g. landscape")
        self.query.textChanged.connect(lambda t: self._set("wallhaven_query", t.strip(), delay=800))
        an.addRow("Wallhaven search", self.query)
        layout.addWidget(self.anime_box)

        form2 = QFormLayout()
        self.keep_days = QSpinBox()
        self.keep_days.setRange(0, 365)
        self.keep_days.setSuffix(" days")
        self.keep_days.setSpecialValueText("Never")
        self.keep_days.setValue(int(self.cfg["delete_after_days"] or 0))
        self.keep_days.valueChanged.connect(lambda v: self._set("delete_after_days", v))
        form2.addRow("Delete downloads after", self.keep_days)
        self.keep_newest = QSpinBox()
        self.keep_newest.setRange(0, 100)
        self.keep_newest.setValue(int(self.cfg["always_keep_newest"] or 0))
        self.keep_newest.valueChanged.connect(lambda v: self._set("always_keep_newest", v))
        form2.addRow("…but always keep the newest", self.keep_newest)
        self.notify = QCheckBox("Tell me when new pictures arrive")
        self.notify.setChecked(bool(self.cfg["show_notification"]))
        self.notify.toggled.connect(lambda on: self._set("show_notification", bool(on)))
        form2.addRow("", self.notify)
        layout.addLayout(form2)

        row = QHBoxLayout()
        fetch = QPushButton("Fetch new pictures now")
        fetch.clicked.connect(self._fetch)
        row.addWidget(fetch)
        row.addStretch(1)
        layout.addLayout(row)
        self.status = _hint("")
        layout.addWidget(self.status)
        layout.addWidget(_hint("Only downloaded files (names starting with auto_) are ever deleted, so pictures "
                               "you add yourself are always safe and always shown."))
        layout.addStretch(1)
        self._show_style()
        self.update_status()

    def _show_style(self):
        anime = self.anime.isChecked()
        self.anime_box.setVisible(anime)
        self.pro_box.setVisible(not anime)

    def _style(self, which):
        """Switching style takes effect at once: the other style's downloads
        leave the rotation, and the wallpaper on screen changes if needed."""
        self._set("style", which)
        self._show_style()
        self.flush()
        mw.taskman.run_on_main(_refresh_gallery)
        if not any(wf.is_style_download(n, which) for n in bg.wallpapers()) and self.per_day.value():
            wf.fetch_now()

    def _topic(self, topic, on):
        if not on and not any(b.isChecked() for b in self.topics.values()) and not self.custom.text().strip():
            self.topics[topic].setChecked(True)  # keep at least one topic (or your own tags)
            return
        self._set("topics", [t for t, b in self.topics.items() if b.isChecked()])

    def update_status(self):
        state = wf.load_state()
        ours = [n for n in bg.wallpapers() if n.startswith(wf.PREFIX)]
        from datetime import date
        today = state.get("count_today", 0) if state.get("last_date") == date.today().isoformat() else 0
        text = f"Downloaded today: {today}. Downloaded pictures of this style: {len(ours)}."
        self.status.setText(text)

    def _fetch(self):
        self.flush()
        wf.fetch_now()

    def _set(self, key, value, delay=300):
        self.cfg[key] = value
        self._save.start(delay)

    def restore_defaults(self):
        d = wf.DEFAULTS
        self.per_day.setValue(d["images_per_day"])
        self.konachan.setChecked(d["use_konachan"])
        self.wallhaven.setChecked(d["use_wallhaven"])
        self.keep_days.setValue(d["delete_after_days"])
        self.keep_newest.setValue(d["always_keep_newest"])
        self.notify.setChecked(d["show_notification"])
        for box in self.topics.values():
            box.setChecked(True)
        self.custom.setText("")
        self.professional.setChecked(True)

    def flush(self):
        self._save.stop()
        try:
            wf.write_config(self.cfg)
        except Exception as exc:
            wf.log(f"could not save settings: {exc}")


# ---------------------------------------------------------------- Glass & sound tab

GLASS_SLIDERS = (
    # key, label, min, max, scale (slider units -> config value), suffix
    ("glass_strength", "Glass opacity", 0, 100, 0.01, "%"),
    ("blur_px", "Blur", 0, 40, 1, " px"),
    ("panel_max_width_px", "Card width", 500, 1600, 1, " px"),
    ("panel_min_height_px", "Card height", 0, 900, 1, " px"),
    ("corner_radius_px", "Corner roundness", 0, 40, 1, " px"),
)
# slider at its lowest = leave the note type's own size alone
TEXT_OFF = 11


class GlassTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = fg.get_config()
        self._save = QTimer(self)
        self._save.setSingleShot(True)
        self._save.timeout.connect(lambda: fg.save_config(self.cfg))
        layout = QVBoxLayout(self)

        card = QGroupBox("Glass card")
        grid = QFormLayout(card)
        self.checks = {}
        box = self._check("glass_enabled", "Show the card on frosted glass")
        grid.addRow(box)
        self.sliders = {}
        for key, label, lo, hi, scale, suffix in GLASS_SLIDERS:
            row, slider = _slider(lo, hi, round(float(self.cfg.get(key, fg.DEFAULTS[key])) / scale), suffix,
                                  lambda v, k=key, s=scale: self._set(k, round(v * s, 2)),
                                  zero_text="Fit to card" if key == "panel_min_height_px" else None)
            if key == "panel_min_height_px":
                slider.setToolTip("The card panel keeps this height on every card (up to the size of the window). "
                                  "Longer cards scroll inside it. Slide all the way left to fit each card instead.")
            grid.addRow(label, row)
            self.sliders[key] = (slider, scale)
        layout.addWidget(card)

        text = QGroupBox("Card text")
        tgrid = QFormLayout(text)
        px = int(self.cfg.get("card_font_px") or 0)
        row, slider = _slider(TEXT_OFF, 48, px if px > TEXT_OFF else TEXT_OFF, " px",
                              lambda v: self._set("card_font_px", 0 if v <= TEXT_OFF else v),
                              zero_text="As in the deck")
        slider.setToolTip("Changes only the size of card text. Bold, italics, colors and layout stay as they are. "
                          "Slide all the way left to use each note type's own size.")
        tgrid.addRow("Text size", row)
        self.text_slider = slider
        layout.addWidget(text)

        answer = QGroupBox("When I answer")
        agrid = QGridLayout(answer)
        agrid.addWidget(self._check("visual_feedback_enabled", "Soft glow around the card"), 0, 0, 1, 3)
        agrid.addWidget(self._check("sound_enabled", "Piano note"), 1, 0, 1, 3)
        agrid.addWidget(QLabel("Volume"), 2, 0)
        row, slider = _slider(0, 100, round(float(self.cfg.get("sound_volume", 0.3)) * 100), "%",
                              lambda v: self._set("sound_volume", round(v / 100, 2)))
        slider.sliderReleased.connect(lambda: fg.play_native("good"))
        self.sliders["sound_volume"] = (slider, 0.01)
        agrid.addLayout(row, 2, 1, 1, 2)
        agrid.addWidget(QLabel("Listen"), 3, 0)
        listen = QHBoxLayout()
        for key in fg.KEYS:
            b = QPushButton(key.capitalize())
            color = fg.get_config()["colors"].get(key, "#999")
            b.setStyleSheet(f"QPushButton {{ border-bottom: 3px solid {color}; }}")
            b.clicked.connect(lambda _c=False, k=key: fg.play_native(k))
            listen.addWidget(b)
        listen.addStretch(1)
        agrid.addLayout(listen, 3, 1, 1, 2)
        agrid.setColumnStretch(1, 1)
        layout.addWidget(answer)

        extra = QHBoxLayout()
        sounds = QPushButton("Use my own sounds…")
        sounds.setToolTip("Put again.wav, hard.wav, good.wav or easy.wav in this folder")
        sounds.clicked.connect(fg.open_sound_folder)
        diag = QPushButton("Copy diagnostics")
        diag.setToolTip("While reviewing: copies details that help fix glass or sound problems")
        diag.clicked.connect(fg.copy_diagnostics)
        extra.addWidget(sounds)
        extra.addWidget(diag)
        extra.addStretch(1)
        layout.addLayout(extra)
        layout.addWidget(_hint("Open a review first, then move the sliders to see the changes on your card as you go."))
        layout.addStretch(1)

    def _check(self, option, label):
        box = QCheckBox(label)
        box.setChecked(bool(self.cfg.get(option, True)))
        box.toggled.connect(lambda on, o=option: self._set(o, bool(on)))
        self.checks[option] = box
        return box

    def _set(self, key, value):
        self.cfg[key] = value
        if key == "sound_volume":
            fg.set_native_volume(value)
        self._save.start(300)
        web = fg.reviewer_web()
        if web:
            web.eval(f"window.fgApply && window.fgApply({json.dumps(fg.page_config(self.cfg))});")
        fg.sync_menu(self.cfg)

    def restore_defaults(self):
        for key, (slider, scale) in self.sliders.items():
            slider.setValue(int(round(fg.DEFAULTS[key] / scale)))
        self.text_slider.setValue(TEXT_OFF)
        for option, box in self.checks.items():
            box.setChecked(fg.DEFAULTS[option])

    def flush(self):
        self._save.stop()
        fg.save_config(self.cfg)


# ---------------------------------------------------------------- window

class SettingsWindow(QDialog):
    def __init__(self, tab=0):
        super().__init__(mw)
        self.setWindowTitle("Frosted Glass")
        self.resize(560, 640)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.wallpaper = WallpaperTab()
        self.downloads = DownloadsTab()
        self.glass = GlassTab()
        self.tabs.addTab(self.wallpaper, "Wallpaper")
        self.tabs.addTab(self.downloads, "Daily downloads")
        self.tabs.addTab(self.glass, "Glass && sound")
        self.tabs.setCurrentIndex(tab)
        layout.addWidget(self.tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        reset = buttons.addButton("Reset this tab", QDialogButtonBox.ButtonRole.ResetRole)
        reset.clicked.connect(lambda: self.tabs.currentWidget().restore_defaults())
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        layout.addWidget(_hint("Changes apply right away and are saved automatically."))
        wf.on_fetched.append(self._fetched)
        bg.on_wallpaper_changed.append(self.wallpaper.follow_new_wallpaper)

    def _fetched(self):
        self.wallpaper.fill_gallery()
        self.downloads.update_status()

    def closeEvent(self, event):
        for tab in (self.wallpaper, self.downloads, self.glass):
            tab.flush()
        if self._fetched in wf.on_fetched:
            wf.on_fetched.remove(self._fetched)
        if self.wallpaper.follow_new_wallpaper in bg.on_wallpaper_changed:
            bg.on_wallpaper_changed.remove(self.wallpaper.follow_new_wallpaper)
        super().closeEvent(event)


_window = None


def _refresh_gallery():
    if _window is not None and _window.isVisible():
        _window.wallpaper.fill_gallery()
    bg.recheck_wallpaper()


def open_settings(tab=0):
    global _window
    if _window is None or not _window.isVisible():
        _window = SettingsWindow(tab)
    else:
        _window.tabs.setCurrentIndex(tab)
    _window.show()
    _window.raise_()
    _window.activateWindow()
