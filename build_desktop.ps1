$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Run start_app.cmd once to create the local Python environment first."
}

& $PythonExe -m pip install -r (Join-Path $ProjectRoot "requirements-desktop.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Desktop dependencies could not be installed."
}
& $PythonExe (Join-Path $ProjectRoot "tools\create_icon.py")
if ($LASTEXITCODE -ne 0) {
    throw "The application icon could not be generated."
}
$ThirdPartyLicenses = Join-Path $ProjectRoot "build\THIRD_PARTY_LICENSES.txt"
& $PythonExe (Join-Path $ProjectRoot "tools\export_third_party_licenses.py") $ThirdPartyLicenses
if ($LASTEXITCODE -ne 0) {
    throw "Third-party licenses could not be exported."
}
& $PythonExe -m PyInstaller --noconfirm --clean `
    --distpath (Join-Path $ProjectRoot "release") `
    --workpath (Join-Path $ProjectRoot "build\desktop") `
    (Join-Path $ProjectRoot "desktop.spec")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build the desktop application."
}

$ReleaseRoot = Join-Path $ProjectRoot "release"
$DesktopFolder = Get-ChildItem -LiteralPath $ReleaseRoot -Directory | Where-Object {
    (Get-ChildItem -LiteralPath $_.FullName -File -Filter "*.exe").Count -gt 0
} | Select-Object -First 1
if (-not $DesktopFolder) {
    throw "The packaged desktop folder was not found."
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") `
    -Destination (Join-Path $DesktopFolder.FullName "README.txt") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") `
    -Destination (Join-Path $DesktopFolder.FullName "LICENSE.txt") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "THIRD_PARTY_NOTICES.md") `
    -Destination (Join-Path $DesktopFolder.FullName "THIRD_PARTY_NOTICES.txt") -Force
Copy-Item -LiteralPath $ThirdPartyLicenses `
    -Destination (Join-Path $DesktopFolder.FullName "THIRD_PARTY_LICENSES.txt") -Force
Write-Host "Desktop build completed in $($DesktopFolder.FullName)"
