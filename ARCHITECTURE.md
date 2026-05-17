# Ci macOS App Architecture

Ci should stay Python/PyInstaller for the first credible macOS app release.

The existing renderer and corpus are already Python-native, and the current app is already a `rumps` menu bar utility. The smallest release-quality move is therefore to harden the Python app rather than split the project into a Swift shell and Python helper. A Swift wrapper can still be revisited later if signing, login items, or permissions become the dominant maintenance cost.

## Runtime Shape

- `ci.py` owns the menu bar app, settings, scheduling, rendering, and wallpaper update.
- `poems.json` is bundled as a PyInstaller data file.
- `qiji-combo.ttf` is bundled when present beside `Ci.spec`; otherwise the app looks for an installed `qiji-combo.ttf` font and shows a clear error if it is missing.
- Generated wallpapers and preferences live under `~/Library/Application Support/Ci`.
- Start-at-login is implemented with a user LaunchAgent at `~/Library/LaunchAgents/com.yankihue.ci.plist`.

## Current Tradeoffs

- This is still a PyInstaller app, so notarization and signing remain separate release work.
- Launch-at-login is pragmatic LaunchAgent support, not the newer Swift `SMAppService` API.
- The app sets all desktops to the generated wallpaper via `osascript`.
- Multi-monitor-specific controls are intentionally out of scope for the MVP.

## Later Upgrade Path

Move to a SwiftUI menu bar shell only if Python packaging becomes the blocker. In that design, Swift should own menu state, preferences, login item registration, and permissions, while Python remains a renderer helper until the rendering code is worth porting.
