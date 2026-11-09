@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_DIR=%~dp0"
set "MODE=--onedir"
set "TRUST_ARGS="
set "SKIP_INSTALL=0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="onefile" set "MODE=--onefile"
if /i "%~1"=="--trust" set "TRUST_ARGS=--trusted-host pypi.python.org --trusted-host files.pythonhosted.org --trusted-host pypi.org"
if /i "%~1"=="--no-install" set "SKIP_INSTALL=1"
if /i "%~1"=="--no-requirements" set "SKIP_INSTALL=1"
shift
goto parse_args

:args_done

if not exist "%PROJECT_DIR%assets\screenshutter.ico" (
    echo ERROR: assets\screenshutter.ico was not found.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%app.py" (
    echo ERROR: app.py was not found.
    pause
    exit /b 1
)

echo.
echo Checking system Python...
py -3 --version
if errorlevel 1 (
    echo ERROR: Python 3 was not found. Install Python and enable the Python Launcher.
    pause
    exit /b 1
)

if "%SKIP_INSTALL%"=="1" (
    echo.
    echo Skipping all package installation as requested.
) else (
    echo.
    echo Installing ScreenShutter requirements and PyInstaller...
    py -3 -m pip install --upgrade -r "%PROJECT_DIR%requirements.txt" pyinstaller %TRUST_ARGS%
    if errorlevel 1 (
        echo ERROR: Package installation failed.
        pause
        exit /b 1
    )
)

echo.
echo Cleaning previous PyInstaller output...
if exist "%PROJECT_DIR%build" rmdir /s /q "%PROJECT_DIR%build"
if exist "%PROJECT_DIR%dist" rmdir /s /q "%PROJECT_DIR%dist"
if exist "%PROJECT_DIR%ScreenShutter.spec" del /q "%PROJECT_DIR%ScreenShutter.spec"

echo.
echo Building ScreenShutter with PyInstaller...
echo Using system Python:
py -3 --version
echo Mode: %MODE%
echo.

py -3 -m PyInstaller %MODE% --noconfirm --clean --windowed --name ScreenShutter --icon="%PROJECT_DIR%assets\screenshutter.ico" --add-data "%PROJECT_DIR%assets\screenshutter.ico;assets" --collect-all pystray --hidden-import=win32com.client --distpath "%PROJECT_DIR%dist" --workpath "%PROJECT_DIR%build\work" --specpath "%PROJECT_DIR%" "%PROJECT_DIR%app.py"

if errorlevel 1 (
    echo.
    echo PyInstaller build failed.
    pause
    exit /b 1
)

if "%MODE%"=="--onefile" (
    if exist "%PROJECT_DIR%dist\ScreenShutter.exe" (
        echo.
        echo Build complete: "%PROJECT_DIR%dist\ScreenShutter.exe"
    ) else (
        echo ERROR: ScreenShutter.exe was not found.
        pause
        exit /b 1
    )
) else (
    if exist "%PROJECT_DIR%dist\ScreenShutter\ScreenShutter.exe" (
        echo.
        echo Build complete: "%PROJECT_DIR%dist\ScreenShutter\ScreenShutter.exe"
    ) else (
        echo ERROR: ScreenShutter.exe was not found in the onedir output.
        pause
        exit /b 1
    )
)

pause
