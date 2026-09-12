[app]
# ROLEX AI v2.2.0 — Android build config (§34-35 Buildozer)
# build:  pip install buildozer  →  buildozer android debug
# apk →   bin/rolex-2.2.0-debug.apk

title = ROLEX AI
package.name = rolex
package.domain = ai.rolex

source.dir = .
source.include_exts = py,json,md,txt,csv,pgconfig,html,css,js,svg
# v2: HUD web assets (rolex/ui/web) ride along for the browser HUD

version = 2.2.0

# v2: pure-stdlib core + Kivy for the Horizon Android UI
requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

# Android permissions (§13/§34: only what's needed — mic for
# 'Hey Guru' wake word, camera for §28 vision, INTERNET for live
# info, notifications for §11 reminders)
android.permissions = RECORD_AUDIO,CAMERA,INTERNET,POST_NOTIFICATIONS
android.api = 34
android.minapi = 24
android.ndk = 25b

# battery / RAM friendly (§13 Android)
android.allow_backup = True
# v2 HUD bridge port on-device (127.0.0.1:8777) — optional, browser only
# export ROLEX_HUD_PORT=8777 && python -m rolex.ui.bridge
osx.python_version = 3.11

# AI keys via build-time env (never hardcode)
# buildozer android debug  # keys loaded from data/secrets.json at runtime

[buildozer]
log_level = 2
warn_on_root = 1

[app:device]  # fast local install when phone connected via adb
debug_deploy = True
