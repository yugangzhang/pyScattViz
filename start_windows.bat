@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo pyScattViz is not installed in this folder yet.
    echo.
    echo Open PowerShell in this folder and follow the Windows installation
    echo section in README.md. The first installation command is:
    echo     py -3.12 -m venv .venv
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pyscattviz %*
set "PYSCATTVIZ_EXIT_CODE=%ERRORLEVEL%"

if not "%PYSCATTVIZ_EXIT_CODE%"=="0" (
    echo.
    echo pyScattViz stopped with an error. The message above may explain the problem.
    pause
)

exit /b %PYSCATTVIZ_EXIT_CODE%
