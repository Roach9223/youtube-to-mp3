# Builds dist\YouTubeToMP3.exe with PyInstaller.
# Run from this folder:  .\build.ps1
# Needs: python, pip install -r requirements.txt pyinstaller

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pyinstaller -q

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "YouTubeToMP3",
    # the three OFL fonts the canvas UI registers at startup
    "--add-data", "fonts;fonts",
    # yt-dlp lazy-loads extractors; pull the whole package in
    "--collect-submodules", "yt_dlp"
)
if (Test-Path "icon.ico") { $pyiArgs += @("--icon", "icon.ico", "--add-data", "icon.ico;.") }

python -m PyInstaller $pyiArgs youtube_to_mp3.py

Write-Host ""
Write-Host "Built dist\YouTubeToMP3.exe"
Write-Host "Ship it with ffmpeg.exe next to it, or tell users to install FFmpeg."
