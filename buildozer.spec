[app]
title = ROLEX AI
package.name = rolex
package.domain = ai.rolex
source.dir = .
source.include_exts = py,json,md,txt,csv,pgconfig,html,css,js,svg
version = 2.2.0
requirements = python3,kivy==2.3.0
orientation = portrait
fullscreen = 0
android.permissions = RECORD_AUDIO,CAMERA,INTERNET,POST_NOTIFICATIONS
android.api = 34
android.minapi = 24
android.ndk = 25b
android.allow_backup = True
osx.python_version = 3.11
[buildozer]
log_level = 2
warn_on_root = 1
[app:device]
debug_deploy = True
