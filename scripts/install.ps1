# Install ytdl on Windows: powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Pratham71/YtDownloader/main/scripts/install.ps1 | iex"
$ErrorActionPreference = "Stop"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

uv tool install --force --python 3.12 git+https://github.com/Pratham71/YtDownloader.git
uv tool update-shell

Write-Host ""
Write-Host "ytdl is installed. Open a new terminal and run: ytdl doctor"
