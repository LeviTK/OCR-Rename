$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[ocr-rename] $Message"
}

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            Exe = "py"
            Args = @("-3")
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Exe = "python"
            Args = @()
        }
    }
    throw "未检测到 Python，请先安装 Python 3.10+"
}

function Test-PythonVersion {
    param($Python)
    & $Python.Exe @($Python.Args + @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"))
    if ($LASTEXITCODE -ne 0) {
        throw "需要 Python 3.10+，当前版本不满足要求"
    }
}

function Resolve-SourceDir {
    $sourceOverride = $env:OCR_RENAME_SOURCE_DIR
    if ($sourceOverride) {
        $sourcePath = (Resolve-Path $sourceOverride).Path
        if (-not (Test-Path (Join-Path $sourcePath "pyproject.toml"))) {
            throw "OCR_RENAME_SOURCE_DIR 缺少 pyproject.toml: $sourcePath"
        }
        return @{
            Path = $sourcePath
            TempRoot = $null
        }
    }

    if ($MyInvocation.MyCommand.Path) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
        if (Test-Path (Join-Path $scriptDir "pyproject.toml")) {
            return @{
                Path = $scriptDir
                TempRoot = $null
            }
        }
    }

    $repo = if ($env:OCR_RENAME_REPO) { $env:OCR_RENAME_REPO } else { "LeviTK/OCR-Rename" }
    $ref = if ($env:OCR_RENAME_REF) { $env:OCR_RENAME_REF } else { "main" }
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ocr-rename-" + [System.Guid]::NewGuid().ToString("N"))
    $archivePath = Join-Path $tempRoot "source.zip"
    $extractRoot = Join-Path $tempRoot "extract"
    $archiveUrl = "https://github.com/$repo/archive/refs/heads/$ref.zip"

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    Write-Info "下载项目源码: $repo@$ref"
    Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath
    Expand-Archive -Path $archivePath -DestinationPath $extractRoot -Force
    $sourceDir = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
    if (-not $sourceDir) {
        throw "下载完成但未找到源码目录"
    }
    return @{
        Path = $sourceDir.FullName
        TempRoot = $tempRoot
    }
}

$repo = if ($env:OCR_RENAME_REPO) { $env:OCR_RENAME_REPO } else { "LeviTK/OCR-Rename" }
$installRoot = if ($env:OCR_RENAME_HOME) { $env:OCR_RENAME_HOME } else { Join-Path $env:LOCALAPPDATA "ocr-rename" }
$binDir = if ($env:OCR_RENAME_BIN_DIR) { $env:OCR_RENAME_BIN_DIR } else { Join-Path $installRoot "bin" }
$appDir = Join-Path $installRoot "app"
$venvDir = Join-Path $installRoot "venv"
$shimPath = Join-Path $binDir "ocr-rename.cmd"
$sourceInfo = $null

try {
    $python = Get-PythonCommand
    Test-PythonVersion -Python $python

    Write-Info "准备安装目录: $installRoot"
    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null

    $sourceInfo = Resolve-SourceDir

    if (Test-Path $appDir) {
        Remove-Item $appDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    Copy-Item -Path (Join-Path $sourceInfo.Path "*") -Destination $appDir -Recurse -Force

    if (Test-Path $venvDir) {
        Remove-Item $venvDir -Recurse -Force
    }

    Write-Info "创建虚拟环境..."
    & $python.Exe @($python.Args + @("-m", "venv", $venvDir))

    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $cliExe = Join-Path $venvDir "Scripts\ocr-rename.exe"

    Write-Info "安装 Python 依赖..."
    & $venvPython -m pip install --upgrade pip setuptools wheel
    & $venvPython -m pip install -e $appDir
    & $cliExe --help | Out-Null

    @"
@echo off
"$cliExe" %*
"@ | Set-Content -Path $shimPath -Encoding Ascii

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $userPathParts = @()
    if (-not [string]::IsNullOrWhiteSpace($userPath)) {
        $userPathParts = $userPath.Split(';') | Where-Object { $_ }
    }
    if (-not ($userPathParts -contains $binDir)) {
        $newUserPath = if ([string]::IsNullOrWhiteSpace($userPath)) { $binDir } else { "$userPath;$binDir" }
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
    }
    if (-not (($env:Path -split ';') -contains $binDir)) {
        $env:Path = "$binDir;$env:Path"
    }

    if (-not (Get-Command tesseract -ErrorAction SilentlyContinue)) {
        Write-Info "未检测到 tesseract，条码/二维码识别仍可用，但 OCR 兜底能力受限"
        Write-Info "建议安装: https://github.com/UB-Mannheim/tesseract/wiki"
    }

    Write-Info "安装完成"
    Write-Info "现在可以直接执行: ocr-rename scan DIR"
} finally {
    if ($sourceInfo -and $sourceInfo.TempRoot -and (Test-Path $sourceInfo.TempRoot)) {
        Remove-Item $sourceInfo.TempRoot -Recurse -Force
    }
}
