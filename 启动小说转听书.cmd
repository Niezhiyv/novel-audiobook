@echo off
setlocal
cd /d "%~dp0"

if exist "小说转听书.exe" (
    start "" "小说转听书.exe"
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m app
    exit /b 0
)

echo 未找到可执行程序或 Python 环境。
echo 请先阅读 README.md 完成安装。
pause
