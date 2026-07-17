$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

if (-not $IsWindows -and $env:OS -ne "Windows_NT") {
    throw "Windows is required to build the YaverVoice EXE artifacts."
}

$requiredFiles = @(
    "package.json",
    "package-lock.json",
    "YaverVoiceSidecar.spec",
    "requirements.txt",
    "requirements-local.txt",
    "requirements-build.txt"
)

foreach ($relativePath in $requiredFiles) {
    if (-not (Test-Path (Join-Path $repoRoot $relativePath))) {
        throw "Required build input was not found: $relativePath"
    }
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    throw "Node.js 24 is required. Install it from https://nodejs.org/ and run npm ci."
}

$nodeVersion = (& node --version).TrimStart("v")
if ($LASTEXITCODE -ne 0 -or [int]($nodeVersion.Split(".")[0]) -ne 24) {
    throw "Node.js 24 is required. Current version: $nodeVersion"
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    throw "npm 11 or newer is required with Node.js 24."
}

$npmVersion = (& npm.cmd --version).Trim()
if ($LASTEXITCODE -ne 0 -or [int]($npmVersion.Split(".")[0]) -lt 11) {
    throw "npm 11 or newer is required. Current version: $npmVersion"
}

if (-not (Test-Path (Join-Path $repoRoot "node_modules\.bin\electron-builder.cmd"))) {
    throw "Node dependencies are missing. Run npm ci from the repository root."
}

$pythonExe = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python virtual environment was not found at venv\Scripts\python.exe. Create it and install requirements.txt, requirements-local.txt, and requirements-build.txt."
}

& $pythonExe -m PyInstaller --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing from venv. Run: python -m pip install -r requirements-build.txt"
}

& $pythonExe -c "import ctranslate2, faster_whisper" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Local Whisper build dependencies are missing from venv. Run: python -m pip install -r requirements-local.txt"
}

$buildTimestamp = Get-Date
$buildVersion = $buildTimestamp.ToString("yyyyMMdd-HHmmss")
$buildTimeDisplay = $buildTimestamp.ToString("yyyy-MM-dd HH:mm:ss")

$gitCommit = "nogit"
try {
    $resolvedCommit = (& git rev-parse --short HEAD 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and $resolvedCommit) {
        $gitCommit = $resolvedCommit
    }
} catch {
}

$gitDirtySuffix = ""
try {
    $gitStatus = (& git status --short 2>$null)
    if ($LASTEXITCODE -eq 0 -and $gitStatus) {
        $gitDirtySuffix = "-dirty"
    }
} catch {
}

$metadataDir = Join-Path $repoRoot "build"
$metadataPath = Join-Path $metadataDir "build_info.json"
$buildLabel = "$buildVersion-$gitCommit$gitDirtySuffix"

New-Item -ItemType Directory -Path $metadataDir -Force | Out-Null
@{
    version = $buildLabel
    build_time = $buildTimeDisplay
    git_commit = $gitCommit
    display = "Build $buildLabel"
} | ConvertTo-Json | Set-Content -Path $metadataPath -Encoding UTF8

$artifactPaths = @(
    (Join-Path $repoRoot "dist\sidecar"),
    (Join-Path $repoRoot "dist-electron"),
    (Join-Path $repoRoot "build\YaverVoiceSidecar")
)

foreach ($path in $artifactPaths) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Recurse -Force
    }
}

& $pythonExe -m PyInstaller --noconfirm --distpath (Join-Path $repoRoot "dist\sidecar") --workpath (Join-Path $repoRoot "build\YaverVoiceSidecar") YaverVoiceSidecar.spec
if ($LASTEXITCODE -ne 0) {
    throw "YaverVoiceSidecar.spec build failed"
}

$sidecarOutput = Join-Path $repoRoot "dist\sidecar\YaverVoiceSidecar.exe"
if (-not (Test-Path $sidecarOutput)) {
    throw "Expected packaged sidecar was not created at $sidecarOutput"
}

$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("yavervoice-build-smoke-" + [guid]::NewGuid().ToString("N"))
$previousAppData = $env:APPDATA
$previousLocalAppData = $env:LOCALAPPDATA

try {
    New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
    $env:APPDATA = $smokeRoot
    $env:LOCALAPPDATA = $smokeRoot

    $statusRequest = '{"jsonrpc":"2.0","id":1,"method":"settings.get_local_whisper_status","params":{}}'
    $statusOutput = @($statusRequest | & $sidecarOutput)
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged sidecar Local Whisper smoke test failed to run."
    }

    $statusResponseLine = $statusOutput | Where-Object { $_ -match '^\s*\{' } | Select-Object -Last 1
    if (-not $statusResponseLine) {
        throw "Packaged sidecar Local Whisper smoke test returned no JSON response."
    }

    $statusResponse = $statusResponseLine | ConvertFrom-Json
    if (-not $statusResponse.result.dependency_available) {
        throw "Packaged sidecar does not contain the Local Whisper runtime dependency."
    }
} finally {
    if ($null -eq $previousAppData) {
        Remove-Item Env:APPDATA -ErrorAction SilentlyContinue
    } else {
        $env:APPDATA = $previousAppData
    }

    if ($null -eq $previousLocalAppData) {
        Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue
    } else {
        $env:LOCALAPPDATA = $previousLocalAppData
    }

    $resolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $resolvedSmokeRoot = [System.IO.Path]::GetFullPath($smokeRoot)
    if ($resolvedSmokeRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path $resolvedSmokeRoot)) {
        Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force
    }
}

& npm.cmd run desktop:build
if ($LASTEXITCODE -ne 0) {
    throw "Electron desktop build failed"
}

$electronOutput = Join-Path $repoRoot "dist-electron"
$desktopArtifacts = @(Get-ChildItem -Path $electronOutput -Filter "*.exe" -File -ErrorAction SilentlyContinue)
if ($desktopArtifacts.Count -lt 2) {
    throw "Expected Windows installer and portable EXE artifacts under $electronOutput"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "Build label: $buildLabel"
Write-Host "Outputs:"
Write-Host "  $sidecarOutput"
foreach ($artifact in $desktopArtifacts) {
    Write-Host "  $($artifact.FullName)"
}
