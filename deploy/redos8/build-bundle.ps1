<#
Запускать на машине С ИНТЕРНЕТОМ (Windows), из корня репозитория:

    powershell -ExecutionPolicy Bypass -File deploy\redos8\build-bundle.ps1 -PythonStandaloneUrl "<URL>"

URL portable-Python нужно взять руками со страницы релизов:
    https://github.com/astral-sh/python-build-standalone/releases
Искать самый свежий релиз, файл вида
    cpython-3.11.<x>+<дата>-x86_64-unknown-linux-gnu-install_only.tar.gz
(НЕ -debug, НЕ -noopt, НЕ freethreaded — обычный install_only build,
собран под glibc, подходит для РЕД ОС 8 x86_64).

Требуется: Python 3.11 (тот же, что в backend/.venv), Node.js/npm,
встроенный в Windows 10/11 tar.exe (есть по умолчанию).

Результат: deploy\redos8\dist\vacation-planner-offline-bundle-<дата>.tar.gz
Перенести на РЕД ОС 8 и распаковать, дальше — install.sh.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$PythonStandaloneUrl
)

$ErrorActionPreference = "Stop"

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$WorkDir = Join-Path $env:TEMP "vacation-bundle-$Stamp"
$BundleDir = Join-Path $WorkDir "bundle"
$OutDir = Join-Path $PSScriptRoot "dist"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

try {
    Write-Host "==> [1/5] Скачиваю portable Python (для РЕД ОС 8, x86_64 glibc)"
    Invoke-WebRequest -Uri $PythonStandaloneUrl -OutFile (Join-Path $BundleDir "python-standalone.tar.gz")

    Write-Host "==> [2/5] Скачиваю wheel-пакеты бэкенда (Linux x86_64, Python 3.11, без сборки из исходников)"
    $WheelhouseDir = Join-Path $BundleDir "wheelhouse"
    New-Item -ItemType Directory -Force -Path $WheelhouseDir | Out-Null
    Push-Location (Join-Path $RootDir "backend")
    try {
        & python -m pip download -d $WheelhouseDir `
            --platform manylinux_2_28_x86_64 `
            --platform manylinux2014_x86_64 `
            --python-version 311 `
            --implementation cp `
            --abi cp311 `
            --only-binary=:all: `
            "pip" "setuptools>=68" "wheel" ".[dev]"
        if ($LASTEXITCODE -ne 0) { throw "pip download завершился с ошибкой" }
    } finally {
        Pop-Location
    }

    Write-Host "==> [3/5] Собираю фронтенд (npm нужен только здесь, не на РЕД ОС)"
    Push-Location (Join-Path $RootDir "frontend")
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci завершился с ошибкой" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build завершился с ошибкой" }
    } finally {
        Pop-Location
    }
    Copy-Item -Recurse (Join-Path $RootDir "frontend\dist") (Join-Path $BundleDir "frontend-dist")

    Write-Host "==> [4/5] Копирую исходники бэкенда (без .venv/__pycache__/egg-info)"
    $BackendDest = Join-Path $BundleDir "app\backend"
    New-Item -ItemType Directory -Force -Path $BackendDest | Out-Null
    robocopy (Join-Path $RootDir "backend") $BackendDest /E `
        /XD .venv __pycache__ .pytest_cache *.egg-info `
        /NFL /NDL /NJH /NJS | Out-Null
    # robocopy возвращает >=8 только при реальных ошибках, 0-7 — норма
    if ($LASTEXITCODE -ge 8) { throw "robocopy завершился с ошибкой ($LASTEXITCODE)" }

    Write-Host "==> [5/5] Кладу конфиги установки и упаковываю бандл"
    Copy-Item (Join-Path $PSScriptRoot "install.sh") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot "nginx-vacation.conf") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot "vacation-backend.service") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot ".env.example") $BundleDir

    $OutFile = Join-Path $OutDir "vacation-planner-offline-bundle-$Stamp.tar.gz"
    Push-Location $BundleDir
    try {
        # tar.exe встроен в Windows 10/11 и Server 2019+
        tar -czf $OutFile .
        if ($LASTEXITCODE -ne 0) { throw "tar завершился с ошибкой" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Готово: $OutFile"
    Write-Host "Перенесите этот файл на РЕД ОС 8, распакуйте в отдельную папку и запустите:"
    Write-Host "  mkdir vacation-bundle && tar xzf $(Split-Path $OutFile -Leaf) -C vacation-bundle"
    Write-Host "  cd vacation-bundle && sudo ./install.sh"
} finally {
    Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
}
