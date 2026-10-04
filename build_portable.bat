@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
if "%PYTHON%"=="" set "PYTHON=python"
"%PYTHON%" "%SCRIPT_DIR%tools\build_portable.py" --project-root "%SCRIPT_DIR%" %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%

