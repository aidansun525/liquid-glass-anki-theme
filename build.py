"""Build dist/frosted_glass_theme.ankiaddon from src/frosted_glass_theme.

    python build.py

The .ankiaddon file is what you upload to AnkiWeb, attach to a GitHub
release, or install with Tools > Add-ons > Install from File.
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src", "frosted_glass_theme")
OUT = os.path.join(ROOT, "dist", "frosted_glass_theme.ankiaddon")
SKIP_DIRS = {"__pycache__", ".git"}
SKIP_FILES = {"meta.json", ".DS_Store"}
SKIP_EXT = (".pyc", ".log", ".part")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, dirs, files in os.walk(SRC):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if name in SKIP_FILES or name.endswith(SKIP_EXT):
                    continue
                path = os.path.join(folder, name)
                zf.write(path, os.path.relpath(path, SRC))
                count += 1
    print(f"wrote {OUT} ({count} files, {os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
