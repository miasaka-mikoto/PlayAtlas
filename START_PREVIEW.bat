@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
echo PlayAtlas browser preview: http://127.0.0.1:8765/preview/
if "%PYTHON%"=="" set "PYTHON=python"
start "PlayAtlas Preview Server" /B cmd /c ""%PYTHON%" "%SCRIPT_DIR%tools\run_headless_smoke.py" --serve --port 8765"
timeout /t 1 /nobreak >nul
start "PlayAtlas Preview" http://127.0.0.1:8765/preview/
echo Close the PlayAtlas Preview Server window to stop the local server.
endlocal
