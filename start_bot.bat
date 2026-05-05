@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python main.py
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 main.py
    goto :end
)

set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%BUNDLED_PY%" (
    "%BUNDLED_PY%" main.py
    goto :end
)

echo Python topilmadi. Python 3.11+ o'rnating: https://www.python.org/downloads/
echo O'rnatishda "Add Python to PATH" ni belgilang.
pause

:end
endlocal
