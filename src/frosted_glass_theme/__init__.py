
# Frosted Glass: wallpapers behind every Anki screen (professional photos
# or anime art, refreshed daily), and a frosted-glass review card with a soft
# glow and piano note on each answer.
#
# Copyright (C) 2026 AidanS
#
# The background part is based on Custom Background Image and Gear Icon by
# ijgnd and The AnKing. License: GNU AGPL, version 3 or later;
# http://www.gnu.org/licenses/agpl.html (see README.txt).

from aqt import mw

# Bring over pictures and settings from add-ons this one replaces (once),
# before anything below picks a wallpaper.
from . import migrate

migrate.run(__name__)

# Serve user_files/ (wallpapers, gears, custom sounds) and web/ to the screens.
mw.addonManager.setWebExports(__name__, r"(user_files.*|web.*)")

from . import background  # noqa: E402,F401
from . import wallpaper_fetcher  # noqa: E402,F401
from . import frosted_glass  # noqa: E402,F401
from . import theme_menu  # noqa: E402,F401
