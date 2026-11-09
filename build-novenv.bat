@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_DIR=%~dp0"
set "MODE=--standalone"
set "TRUST_ARGS="
set "SKIP_REQUIREMENTS=0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="onefile" set "MODE=--onefile"
if /i "%~1"=="--trust" set "TRUST_ARGS=--trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host pypi.org"
if /i "%~1"=="--no-requirements" set "SKIP_REQUIREMENTS=1"
shift
goto parse_args

:args_done

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
echo Checking system Python...
py -3 --version
if errorlevel 1 (
    echo.
    echo ERROR: Python 3 was not found. Install Python and enable the Python Launcher.
    pause
    exit /b 1
)

echo.
if "%SKIP_REQUIREMENTS%"=="1" (
    echo Skipping requirements.txt installation as requested.
    echo Installing Nuitka only...
    py -3 -m pip install --upgrade nuitka %TRUST_ARGS%
) else (
    echo Installing ScreenShutter requirements and Nuitka into the active Python installation...
    py -3 -m pip install --upgrade -r "%PROJECT_DIR%requirements.txt" nuitka %TRUST_ARGS%
)
if errorlevel 1 (
    echo.
    echo Package installation failed.
    pause
    exit /b 1
)

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
echo Using system Python:
py -3 --version
echo Mode: %MODE%
echo.

py -3 -m nuitka %MODE% ^
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
if "%MODE%"=="--onefile" (
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
