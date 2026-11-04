@echo off
setlocal
cd /d "%~dp0"

echo Installing ScreenShutter dependencies and Nuitka...
py -m pip install --upgrade -r requirements.txt nuitka
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

set "MODE=--standalone"
if /i "%~1"=="onefile" set "MODE=--onefile"

echo.
echo Building ScreenShutter (%MODE%)...
py -m nuitka %MODE% ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=disable ^
    --output-dir=build ^
    --output-filename=ScreenShutter.exe ^
    --include-package=pystray ^
    --include-package=PIL ^
    --include-package=win32com.client ^
    app.py

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
if /i "%~1"=="onefile" (
    echo Build complete: build\ScreenShutter.exe
) else (
    echo Build complete: build\ScreenShutter.dist\ScreenShutter.exe
)
pause
