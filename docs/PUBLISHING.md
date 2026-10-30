# Publishing checklist

## Before the first release

1. **Unsplash key.** At [unsplash.com/developers](https://unsplash.com/developers), click *New Application* and name it **Frosted Glass Anki**. Copy its **Access Key** (not the Secret Key) into `UNSPLASH_APP_KEY` in `src/frosted_glass_theme/wallpaper_fetcher/__init__.py`.
   - A new app starts in *demo* mode, which allows 50 requests an hour shared by all users. Each user needs about one request a day.
   - Once people are using the add-on, open the app's page and click **Apply for production** to get 5,000 requests an hour. Unsplash checks that photos load from Unsplash, that the photographer and Unsplash are credited, and that downloads are reported. The add-on already does all three. Their review asks for a screenshot of the credit, which you can take on the deck list while an Unsplash photo is showing.
2. **Built-in wallpapers.** Replace the three files in `src/frosted_glass_theme/user_files/default_wallpapers/` if you like, keeping the `Default - ` prefix. Use only pictures you're allowed to share, such as your own or Unsplash photos (the Unsplash License allows this; credit the photographer in the README).
3. **Version.** Set `human_version` in `src/frosted_glass_theme/manifest.json` and add a line to `CHANGELOG.md`.
4. **Build.** Run `python build.py`, which writes `dist/frosted_glass_theme.ankiaddon`.
5. **Test.** In Anki, go to Tools → Add-ons → Install from File…, pick the file and restart Anki. Then check a review and the Settings window.

## AnkiWeb

1. Sign in at [ankiweb.net](https://ankiweb.net) and open [Share an add-on](https://ankiweb.net/shared/upload).
2. Fill in the fields:
   - **Title:** `Frosted Glass: Anki Aesthetic Overhaul`
   - **Tags:** `theme background wallpaper glass aesthetic reviewer sound`
   - **Support page:** `https://github.com/aidansun525/liquid-glass-anki-theme/issues`
   - **Description:** paste the contents of `docs/ankiweb_description.html`. The images load from GitHub, so push the repo first.
   - **File:** `dist/frosted_glass_theme.ankiaddon`.
3. After uploading, AnkiWeb gives the add-on a number (its install code). Put the AnkiWeb link and code into the Install section of `README.md`.
4. For later updates, use the same page's *Update* option with a new build. Users get the update automatically.

## GitHub release

1. Push to `main`.
2. Go to Releases → *Draft a new release*. Use the tag `v1.0`, title it `1.0`, paste the changelog entry, and attach `dist/frosted_glass_theme.ankiaddon`.
