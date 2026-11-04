@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0app.py" (
    echo ERROR: app.py was not found in:
    echo %~dp0
    pause
    exit /b 1
)

echo Installing ScreenShutter dependencies and Nuitka...
py -m pip install --upgrade -r "%~dp0requirements.txt" nuitka
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

set "MODE=--standalone"
set "OUTPUT=ScreenShutter.dist"
if /i "%~1"=="onefile" (
    set "MODE=--onefile"
    set "OUTPUT=ScreenShutter.exe"
)

echo.
echo Cleaning previous ScreenShutter build...
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if exist "%~dp0build" (
    echo Could not clean the previous build directory.
    pause
    exit /b 1
)

echo.
echo Building ScreenShutter from:
echo "%~dp0app.py"
echo Mode: %MODE%
echo.
py -m nuitka %MODE% ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=disable ^
    --output-dir="%~dp0build" ^
    --output-filename=ScreenShutter.exe ^
    --include-package=pystray ^
    --include-package=PIL ^
    --include-package=win32com.client ^
    "%~dp0app.py"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
if /i "%~1"=="onefile" (
    if exist "%~dp0build\ScreenShutter.exe" (
        echo Build complete: "%~dp0build\ScreenShutter.exe"
    ) else (
        echo ERROR: Nuitka finished, but ScreenShutter.exe was not found.
        pause
        exit /b 1
    )
) else (
    if exist "%~dp0build\ScreenShutter.dist\ScreenShutter.exe" (
        echo Build complete: "%~dp0build\ScreenShutter.dist\ScreenShutter.exe"
    ) else (
        echo ERROR: Nuitka finished, but the standalone executable was not found.
        pause
        exit /b 1
    )
)
pause
