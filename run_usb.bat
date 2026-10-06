@echo off
setlocal
cd /d "%~dp0"
if exist "apps\user_app\pubspec.yaml" (
    cd apps\user_app
)
echo ========================================================
echo Starting Veriqoo on USB Android Device (AG2SEI24DB007876)...
echo ========================================================
flutter run -d AG2SEI24DB007876 --dart-define-from-file=dart_defines.json %*
