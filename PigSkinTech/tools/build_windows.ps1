param(
    [string]$PythonPath = '..\.venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$resolvedPython = Resolve-Path -LiteralPath (Join-Path $projectRoot $PythonPath)

& $resolvedPython -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed in the selected build environment. No package was created.'
}

Push-Location $projectRoot
try {
    & $resolvedPython -m PyInstaller --noconfirm --clean .\PigSkinAIStudio.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Output (Join-Path $projectRoot 'dist\PigSkinAIStudio.exe')
