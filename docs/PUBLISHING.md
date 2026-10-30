# Publishing checklist

## Before the first release

1. **Built-in wallpapers.** These are the four files in `src/frosted_glass_theme/user_files/default_wallpapers/`. To change them, keep the `Default - ` prefix, and use only pictures you're allowed to share, such as your own photos.
2. **Version.** Set `human_version` in `src/frosted_glass_theme/manifest.json` and add a line to `CHANGELOG.md`.
3. **Build.** Run `python build.py`, which writes `dist/frosted_glass_theme.ankiaddon`.
4. **Test.** In Anki, go to Tools → Add-ons → Install from File…, pick the file and restart Anki. Then check a review and the Settings window.

## AnkiWeb

1. Sign in at [ankiweb.net](https://ankiweb.net) and open [Share an add-on](https://ankiweb.net/shared/upload).
2. Fill in the fields:
   - **Title:** `Frosted Glass: Anki Aesthetic Overhaul`
   - **Tags:** `theme background wallpaper glass aesthetic reviewer sound`
   - **Support page:** `https://github.com/aidansun525/liquid-glass-anki-theme/issues`
   - **Description:** paste the contents of `docs/ankiweb_description.md` (or the `.html` version if the field doesn't render Markdown). The images load from GitHub, so push the repo first.
   - **File:** `dist/frosted_glass_theme.ankiaddon`.
3. After uploading, AnkiWeb gives the add-on a number (its install code). Put the AnkiWeb link and code into the Install section of `README.md`.
4. For later updates, use the same page's *Update* option with a new build. Users get the update automatically.

## GitHub release

1. Push to `main`.
2. Go to Releases → *Draft a new release*. Use the tag `v1.0`, title it `1.0`, paste the changelog entry, and attach `dist/frosted_glass_theme.ankiaddon`.
