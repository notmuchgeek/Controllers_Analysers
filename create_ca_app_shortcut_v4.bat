@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%run_ca_app.py"
set "SHORTCUT_PATH=%SCRIPT_DIR%ca_app.lnk"
set "ICON_PATH=%SCRIPT_DIR%src\ca_app\icon\cat_memo_laser_analyser_icon.ico"

if not exist "%SCRIPT_PATH%" (
    echo ERROR: run_ca_app.py not found in:
    echo %SCRIPT_DIR%
    pause
    exit /b 1
)

echo.
echo Paste the python.exe path, or paste the Anaconda folder path.
echo Example: C:\anaconda3\python.exe
set /p "PYTHON_INPUT=> "

if not defined PYTHON_INPUT (
    call :TryAutoDetect
) else (
    for %%I in ("%PYTHON_INPUT%") do set "PYTHON_INPUT=%%~fI"
    if exist "%PYTHON_INPUT%\python.exe" (
        set "PYTHON_EXE=%PYTHON_INPUT%\python.exe"
    ) else if exist "%PYTHON_INPUT%" (
        set "PYTHON_EXE=%PYTHON_INPUT%"
    ) else (
        call :TryAutoDetect
    )
)

if not defined PYTHON_EXE (
    echo.
    echo ERROR: could not find python.exe.
    echo You can enter either:
    echo   1^) full path to python.exe
    echo   2^) folder containing python.exe
    echo.
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo.
    echo ERROR: python.exe not found:
    echo %PYTHON_EXE%
    pause
    exit /b 1
)

echo.
echo Using:
echo %PYTHON_EXE%

echo.
if not exist "%ICON_PATH%" (
    echo WARNING: icon file not found:
    echo %ICON_PATH%
    echo Shortcut will be created without a custom icon.
    set "ICON_PATH="
)

set "VBS_FILE=%TEMP%\create_shortcut_%RANDOM%%RANDOM%.vbs"
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo Set Shortcut = WshShell.CreateShortcut^("%SHORTCUT_PATH%"^)
    echo Shortcut.TargetPath = "%PYTHON_EXE%"
    echo Shortcut.Arguments = Chr^(34^) ^& "%SCRIPT_PATH%" ^& Chr^(34^)
    echo Shortcut.WorkingDirectory = "%SCRIPT_DIR%"
    if defined ICON_PATH echo Shortcut.IconLocation = "%ICON_PATH%,0"
    echo Shortcut.Save
) > "%VBS_FILE%"

echo.
echo Creating shortcut...
cscript //nologo "%VBS_FILE%"
set "ERR=%ERRORLEVEL%"

del "%VBS_FILE%" >nul 2>nul

if not "%ERR%"=="0" (
    echo.
    echo ERROR: failed to create shortcut.
    pause
    exit /b %ERR%
)

echo.
echo Shortcut created:
echo %SHORTCUT_PATH%
pause
endlocal
exit /b 0

:TryAutoDetect
set "PYTHON_EXE="
for %%P in (
    "C:\anaconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
) do (
    if exist %%~P (
        set "PYTHON_EXE=%%~P"
        goto :eof
    )
)
for /f "delims=" %%P in ('where python 2^>nul') do (
    set "PYTHON_EXE=%%P"
    goto :eof
)
goto :eof
