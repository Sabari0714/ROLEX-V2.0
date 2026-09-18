[app]
# Rolex V 2.0 — Android build config
# build: pip install buildozer -> buildozer android debug
# apk: bin/rolex-2.2.0-debug.apk

title = Rolex V 2.0
package.name = rolexv2
package.domain = ai.rolexv2

source.dir = .
source.include_exts = py,json,md,txt,csv,pgconfig,html,css,js,svg,png
version = 2.0.0

# Pure-stdlib core + Kivy Android UI
requirements = python3,kivy==2.3.1

orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = RECORD_AUDIO,CAMERA,INTERNET,POST_NOTIFICATIONS
android.api = 34
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True

# Pin python-for-android to a stable release compatible with the packaged Kivy UI
# support. This avoids pulling an incompatible moving/develop toolchain.
p4a.branch = v2024.01.21

# Modern Android phones are arm64; keeping one ABI makes CI builds
# smaller and avoids unnecessary legacy-ABI recipe compilation.
android.archs = arm64-v8a

android.allow_backup = True

# AI keys are loaded at runtime; never hardcode secrets in this file.

[buildozer]
log_level = 2
warn_on_root = 1

[app:device]
debug_deploy = True
