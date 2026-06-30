@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_PATH=%SCRIPT_DIR%run_ca_app.py"
set "SETUP_PATH=%SCRIPT_DIR%setup_ca_app.py"
set "REQUIREMENTS_PATH=%SCRIPT_DIR%requirements.txt"
set "WHEELHOUSE_PATH=%SCRIPT_DIR%wheelhouse"
set "SHORTCUT_PATH=%SCRIPT_DIR%ca_app.lnk"
set "ICON_PATH=%SCRIPT_DIR%src\ca_app\icon\cat_memo_laser_analyser_icon.ico"

if not exist "%SCRIPT_PATH%" (
    echo ERROR: run_ca_app.py not found in:
    echo %SCRIPT_DIR%
    pause
    exit /b 1
)

if not exist "%SETUP_PATH%" (
    echo ERROR: setup_ca_app.py not found in:
    echo %SCRIPT_DIR%
    pause
    exit /b 1
)

if not exist "%REQUIREMENTS_PATH%" (
    echo ERROR: requirements.txt not found in:
    echo %SCRIPT_DIR%
    pause
    exit /b 1
)

if not exist "%WHEELHOUSE_PATH%\" (
    echo ERROR: wheelhouse folder not found in:
    echo %SCRIPT_DIR%
    pause
    exit /b 1
)

echo.
echo Paste the python.exe path, or paste the Anaconda folder path.
echo Example: C:\anaconda3\python.exe
echo Press Enter to search automatically.
set /p "PYTHON_INPUT=> "
set "PYTHON_INPUT=%PYTHON_INPUT:"=%"

if not defined PYTHON_INPUT (
    call :TryAutoDetect
) else (
    for %%I in ("%PYTHON_INPUT%") do call :ResolvePythonInput "%%~fI"
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
"%PYTHON_EXE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo.
    echo ERROR: Controllers ^& Analysers requires Python 3.10 or newer.
    echo Select a newer Python or Anaconda installation.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import sys; print('Python version:', sys.version.split()[0])"

echo.
echo Checking application requirements...
"%PYTHON_EXE%" "%SETUP_PATH%"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo ERROR: requirements could not be prepared.
    echo The shortcut was not created. Review the messages above and try again.
    pause
    exit /b %ERR%
)

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

:ResolvePythonInput
if exist "%~1\python.exe" (
    set "PYTHON_EXE=%~1\python.exe"
) else if exist "%~1" (
    set "PYTHON_EXE=%~1"
) else (
    call :TryAutoDetect
)
goto :eof

:TryAutoDetect
set "PYTHON_EXE="
for %%P in (
    "C:\anaconda3\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) do (
    if exist "%%~P" (
        call :ConsiderPython "%%~P"
        if defined PYTHON_EXE goto :eof
    )
)

for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do (
    call :ConsiderPython "%%P"
    if defined PYTHON_EXE goto :eof
)

for /f "delims=" %%P in ('where python 2^>nul') do (
    call :ConsiderPython "%%P"
    if defined PYTHON_EXE goto :eof
)
goto :eof

:ConsiderPython
if not exist "%~1" goto :eof
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_EXE=%~1"
goto :eof
