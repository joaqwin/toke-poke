# Compila Toke-Poke a .exe y genera el instalador.
#   powershell -ExecutionPolicy Bypass -File build.ps1
# Requisitos: pip install -r requirements-dev.txt  e  Inno Setup 6 (winget install JRSoftware.InnoSetup)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/3 Icono" -ForegroundColor Cyan
$env:QT_QPA_PLATFORM = "offscreen"
python make_icon.py
Remove-Item Env:QT_QPA_PLATFORM

Write-Host "== 2/3 PyInstaller" -ForegroundColor Cyan
if (Test-Path dist\TokePoke) { Remove-Item -Recurse -Force dist\TokePoke }
python -m PyInstaller --noconfirm --clean toke_poke.spec
if (-not (Test-Path dist\TokePoke\TokePoke.exe)) { throw "No se generó dist\TokePoke\TokePoke.exe" }

Write-Host "== 3/3 Instalador (Inno Setup)" -ForegroundColor Cyan
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) {
        Write-Warning "Inno Setup no encontrado: se omite el instalador. Ejecutable listo en dist\TokePoke\TokePoke.exe"
        exit 0
    }
    $isccPath = $found
} else {
    $isccPath = $iscc.Source
}
& $isccPath /Q installer.iss
Get-ChildItem dist\installer\*.exe | ForEach-Object {
    Write-Host ("Instalador: {0} ({1:N1} MB)" -f $_.FullName, ($_.Length / 1MB)) -ForegroundColor Green
}
