$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到 .venv。请先运行：uv sync --all-groups"
}

$modelPath = Join-Path $root "models\kokoro\kokoro-v1.1-zh.int8.onnx"
$voicesPath = Join-Path $root "models\kokoro\voices-v1.1-zh.bin"
if (-not (Test-Path -LiteralPath $modelPath) -or -not (Test-Path -LiteralPath $voicesPath)) {
    throw "Kokoro 模型文件不完整。请先按 docs\kokoro-setup.md 放置模型。"
}

$originalPath = $env:PATH
$env:PATH = @(
    (Join-Path $env:SystemRoot "System32"),
    $env:SystemRoot,
    (Join-Path $env:SystemRoot "System32\Wbem"),
    (Split-Path $python),
    (Join-Path $root ".venv\Scripts")
) -join ";"
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "小说转听书" `
        --specpath "build" `
        --paths $root `
        --collect-all kokoro_onnx `
        --collect-all espeakng_loader `
        --collect-all phonemizer `
        app\__main__.py
    $buildExitCode = $LASTEXITCODE
}
finally {
    $env:PATH = $originalPath
}

if ($buildExitCode -ne 0) {
    throw "PyInstaller 构建失败，退出码：$buildExitCode"
}

Copy-Item -LiteralPath (Join-Path $root "dist\小说转听书.exe") -Destination (Join-Path $root "小说转听书.exe") -Force
Write-Host "构建完成：$root\小说转听书.exe"
