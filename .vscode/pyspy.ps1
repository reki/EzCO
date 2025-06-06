# py-spy helper for Windows.
# .venv\Scripts\python.exe is venvlauncher, which py-spy cannot inspect.
# Profile the base interpreter instead, with the venv site-packages on PYTHONPATH.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("top", "record-svg", "record-speedscope")]
    [string]$Mode
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cfg = Join-Path $root ".venv\pyvenv.cfg"
if (-not (Test-Path $cfg)) {
    throw "venv not found: $cfg"
}

$basePython = $null
Get-Content -LiteralPath $cfg | ForEach-Object {
    if ($_ -match '^\s*base-executable\s*=\s*(.+?)\s*$') {
        $basePython = $Matches[1]
    }
    elseif (-not $basePython -and $_ -match '^\s*home\s*=\s*(.+?)\s*$') {
        $basePython = Join-Path $Matches[1] "python.exe"
    }
}
if (-not $basePython -or -not (Test-Path -LiteralPath $basePython)) {
    throw "base Python not found (pyvenv.cfg). got: $basePython"
}

$venv = Join-Path $root ".venv"
$pySpy = Join-Path $venv "Scripts\py-spy.exe"
if (-not (Test-Path -LiteralPath $pySpy)) {
    throw "py-spy not found: $pySpy"
}

$env:VIRTUAL_ENV = $venv
$env:PYTHONPATH = "$(Join-Path $root 'src');$(Join-Path $venv 'Lib\site-packages')"
$env:PATH = "$(Join-Path $venv 'Scripts');$env:PATH"
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue

$pythonArgs = @("--", $basePython, "-m", "ez_co.main")
Set-Location -LiteralPath $root

switch ($Mode) {
    "top" {
        & $pySpy top @pythonArgs
    }
    "record-svg" {
        & $pySpy record -o (Join-Path $root "py-spy-ezco.svg") -f flamegraph --full-filenames @pythonArgs
    }
    "record-speedscope" {
        & $pySpy record -o (Join-Path $root "py-spy-ezco.speedscope.json") -f speedscope --full-filenames @pythonArgs
    }
}

exit $LASTEXITCODE
