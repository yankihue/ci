# Ci

<img width="1800" alt="Desktop image showing an example generated background" src="https://user-images.githubusercontent.com/61288822/221179105-ad1926fa-40c2-47a2-addf-18e14cc1c4d3.png">

Ci is a macOS menu bar app that generates classical Chinese poetry wallpapers from `唐詩三百首`.

## Features

- Menu bar control for generating a new wallpaper.
- Pause and resume scheduling.
- Interval choices: 10 minutes, 30 minutes, 1 hour, or daily.
- Current poem title and text shown in the menu.
- Finder shortcut for the generated wallpaper file.
- Optional start-at-login support.
- Preferences and generated wallpaper stored in `~/Library/Application Support/Ci`.

## Font Requirement

Ci uses [齊伋體 qiji-font](https://github.com/LingDong-/qiji-font). The recommended file is `qiji-combo.ttf`.

For local use, install `qiji-combo.ttf` with Font Book. For release builds, place `qiji-combo.ttf` next to `Ci.spec` before running PyInstaller. The build will bundle it when present. If the app cannot find the font, it shows a menu bar error alert instead of failing silently.

## Installation

Download the latest DMG from the [GitHub releases page](https://github.com/yankihue/ci/releases), open it, and drag `Ci.app` to Applications.

Because unsigned local builds are not notarized, macOS may require opening the app from Finder with Control-click, then Open.

## Usage

After launch, Ci appears as `词` in the menu bar.

- `New Wallpaper` immediately renders and applies a new wallpaper.
- `Pause` stops scheduled changes.
- `Current Poem` shows the title, author, and poem text from the last generated wallpaper.
- `Reveal Wallpaper` opens the generated wallpaper in Finder.
- `Interval` controls the automatic refresh cadence.
- `Start at Login` creates or removes `~/Library/LaunchAgents/com.yankihue.ci.plist`.

## Development

Install dependencies:

```bash
poetry env use python3.10
poetry install
```

Run from source:

```bash
poetry run python ci.py
```

Build the app:

```bash
PYINSTALLER_CONFIG_DIR=.pyinstaller-cache poetry run pyinstaller -y --clean Ci.spec
```

Create a DMG:

```bash
brew install create-dmg
./builddmg.sh
```

The DMG is written to `dist/Ci.dmg`.

## Release Notes

Minimum credible local release:

```bash
PYINSTALLER_CONFIG_DIR=.pyinstaller-cache poetry run pyinstaller -y --clean Ci.spec
codesign --force --deep --sign - dist/Ci.app
./builddmg.sh
codesign --force --sign - dist/Ci.dmg
```

Public distribution should use a paid Apple Developer certificate and notarization. Do not treat the ad-hoc signing command above as a notarized release.

## Troubleshooting

If wallpaper generation fails with a missing font message, install `qiji-combo.ttf` or rebuild with the font beside `Ci.spec`.

If start-at-login does not work, remove `~/Library/LaunchAgents/com.yankihue.ci.plist`, launch Ci manually, and enable `Start at Login` again.

If the app launches but no wallpaper changes, check that macOS allowed the AppleScript desktop update. Running from Terminal with `poetry run python ci.py` will print the generated poem and output path.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the current Python/PyInstaller decision and the future Swift-shell upgrade path.
