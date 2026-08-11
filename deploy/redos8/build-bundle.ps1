<#
Run on a machine WITH INTERNET (Windows), from the repository root:

    powershell -ExecutionPolicy Bypass -File deploy\redos8\build-bundle.ps1 -PythonStandaloneUrl "<URL>"

Get the portable-Python URL manually from the releases page:
    https://github.com/astral-sh/python-build-standalone/releases
Look for the latest release, a file named like:
    cpython-3.11.<x>+<date>-x86_64-unknown-linux-gnu-install_only.tar.gz

Must contain "unknown-linux-gnu" (NOT "musl" — RED OS 8 uses glibc, not musl)
and plain "x86_64" (NOT "x86_64_v2/_v3/_v4" — those need a newer CPU with
AVX2/AVX-512 and may not run on the target server). Also avoid -debug,
-noopt, freethreaded variants — use the plain install_only build.

Requires: Python 3.11 (same one used for backend/.venv), Node.js/npm,
tar.exe (built into Windows 10/11 by default).

Output: deploy\redos8\dist\vacation-planner-offline-bundle-<timestamp>.tar.gz
Transfer that file to RED OS 8 and unpack it, then run install.sh.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$PythonStandaloneUrl,
    [switch]$AllowUnsupportedPythonBuild
)

$ErrorActionPreference = "Stop"

$urlProblems = @()
if ($PythonStandaloneUrl -match "musl") {
    $urlProblems += "contains 'musl' - RED OS 8 uses glibc, this build will NOT run there"
}
if ($PythonStandaloneUrl -match "x86_64_v[234]") {
    $urlProblems += "targets a specific CPU microarchitecture level (v2/v3/v4) - crashes with 'Illegal instruction' on CPUs/VMs without that feature set (e.g. no AVX-512)"
}
if ($urlProblems.Count -gt 0) {
    Write-Host "The Python URL looks wrong for RED OS 8:" -ForegroundColor Red
    foreach ($p in $urlProblems) { Write-Host "  - $p" -ForegroundColor Red }
    Write-Host "Expected a file named like: cpython-3.11.<x>+<date>-x86_64-unknown-linux-gnu-install_only.tar.gz" -ForegroundColor Yellow
    if (-not $AllowUnsupportedPythonBuild) {
        throw "Refusing to build with this URL. Pick the plain 'x86_64-unknown-linux-gnu' asset, or pass -AllowUnsupportedPythonBuild if you are certain this is correct for your target machine."
    }
    Write-Host "Continuing anyway because -AllowUnsupportedPythonBuild was passed." -ForegroundColor Yellow
}

$RootDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$WorkDir = Join-Path $env:TEMP "vacation-bundle-$Stamp"
$BundleDir = Join-Path $WorkDir "bundle"
$OutDir = Join-Path $PSScriptRoot "dist"

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

try {
    Write-Host "==> [1/5] Downloading portable Python (for RED OS 8, x86_64 glibc)"
    Invoke-WebRequest -Uri $PythonStandaloneUrl -OutFile (Join-Path $BundleDir "python-standalone.tar.gz")

    Write-Host "==> [2/5] Downloading backend wheel packages (Linux x86_64, Python 3.11, prebuilt only)"
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
        if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
    } finally {
        Pop-Location
    }

    Write-Host "==> [3/5] Building frontend (npm is only needed here, not on RED OS)"
    Push-Location (Join-Path $RootDir "frontend")
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    } finally {
        Pop-Location
    }
    Copy-Item -Recurse (Join-Path $RootDir "frontend\dist") (Join-Path $BundleDir "frontend-dist")

    Write-Host "==> [4/5] Copying backend source (excluding .venv/__pycache__/egg-info)"
    $BackendDest = Join-Path $BundleDir "app\backend"
    New-Item -ItemType Directory -Force -Path $BackendDest | Out-Null
    robocopy (Join-Path $RootDir "backend") $BackendDest /E `
        /XD .venv __pycache__ .pytest_cache *.egg-info `
        /NFL /NDL /NJH /NJS | Out-Null
    # robocopy exit codes 0-7 are success, >=8 means a real error
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }

    Write-Host "==> [5/5] Adding install configs and packing the bundle"
    Copy-Item (Join-Path $PSScriptRoot "install.sh") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot "nginx-vacation.conf") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot "vacation-backend.service") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot ".env.example") $BundleDir
    Copy-Item (Join-Path $PSScriptRoot "README.md") $BundleDir

    $OutFile = Join-Path $OutDir "vacation-planner-offline-bundle-$Stamp.tar.gz"
    Push-Location $BundleDir
    try {
        # tar.exe is built into Windows 10/11 and Server 2019+
        tar -czf $OutFile .
        if ($LASTEXITCODE -ne 0) { throw "tar failed" }
    } finally {
        Pop-Location
    }

    Write-Host ""
    Write-Host "Done: $OutFile"
    Write-Host "Transfer this file to RED OS 8, unpack it into its own folder, then run:"
    Write-Host "  mkdir vacation-bundle && tar xzf $(Split-Path $OutFile -Leaf) -C vacation-bundle"
    Write-Host "  cd vacation-bundle && sudo ./install.sh"
} finally {
    Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
}
