@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_DIR=%~dp0"
set "VENV_DIR=%PROJECT_DIR%.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

if not exist "%PROJECT_DIR%assets\screenshutter.ico" (
    echo ERROR: assets\screenshutter.ico was not found.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%app.py" (
    echo ERROR: app.py was not found in:
    echo %PROJECT_DIR%
    pause
    exit /b 1
)

echo.
echo Checking ScreenShutter virtual environment...
if not exist "%VENV_PYTHON%" (
    echo Creating virtual environment in:
    echo "%VENV_DIR%"
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo.
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment Python was not created.
    pause
    exit /b 1
)

echo.
echo Installing ScreenShutter dependencies and Nuitka into the virtual environment...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo Could not upgrade pip.
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install --upgrade -r "%PROJECT_DIR%requirements.txt" nuitka
if errorlevel 1 (
    echo.
    echo Dependency installation failed.
    pause
    exit /b 1
)

set "MODE=--standalone"
if /i "%~1"=="onefile" set "MODE=--onefile"

echo.
echo Cleaning previous ScreenShutter build...
if exist "%PROJECT_DIR%build" rmdir /s /q "%PROJECT_DIR%build"
if exist "%PROJECT_DIR%build" (
    echo Could not clean the previous build directory.
    pause
    exit /b 1
)

echo.
echo Building ScreenShutter from:
echo "%PROJECT_DIR%app.py"
echo Using Python:
echo "%VENV_PYTHON%"
echo Mode: %MODE%
echo.

"%VENV_PYTHON%" -m nuitka %MODE% ^
    --enable-plugin=tk-inter ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico="%PROJECT_DIR%assets\screenshutter.ico" ^
    --include-data-files="%PROJECT_DIR%assets\screenshutter.ico=assets/screenshutter.ico" ^
    --output-dir="%PROJECT_DIR%build" ^
    --output-filename=ScreenShutter.exe ^
    --include-package=pystray ^
    --include-package=PIL ^
    --include-package=win32com.client ^
    "%PROJECT_DIR%app.py"

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
if /i "%~1"=="onefile" (
    if exist "%PROJECT_DIR%build\ScreenShutter.exe" (
        echo Build complete: "%PROJECT_DIR%build\ScreenShutter.exe"
    ) else (
        echo ERROR: Nuitka finished, but ScreenShutter.exe was not found.
        pause
        exit /b 1
    )
) else (
    if exist "%PROJECT_DIR%build\ScreenShutter.dist\ScreenShutter.exe" (
        echo Build complete: "%PROJECT_DIR%build\ScreenShutter.dist\ScreenShutter.exe"
    ) else (
        echo ERROR: Nuitka finished, but the standalone executable was not found.
        pause
        exit /b 1
    )
)
pause
