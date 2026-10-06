param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$FlutterArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (Test-Path "$scriptDir\apps\user_app\pubspec.yaml") {
    Set-Location "$scriptDir\apps\user_app"
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting Veriqoo on USB Android Device (AG2SEI24DB007876)..." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

flutter run -d AG2SEI24DB007876 --dart-define-from-file=dart_defines.json $FlutterArgs
