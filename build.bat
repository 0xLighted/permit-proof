@echo off
setlocal
echo ================================================================
echo   PERMITPROOF FRONTEND BUILD
echo ================================================================

where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: 'npm' was not found on your system PATH.
    echo Please install Node.js to compile the frontend.
    exit /b 1
)

cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo [1/2] Installing frontend dependencies via npm install...
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo ERROR: npm install failed.
        exit /b %ERRORLEVEL%
    )
) else (
    echo [1/2] Dependencies already installed in node_modules.
)

echo [2/2] Compiling production bundle via npm run build...
call npm run build
if %ERRORLEVEL% neq 0 (
    echo ERROR: npm run build failed.
    exit /b %ERRORLEVEL%
)

echo.
echo ================================================================
echo   FRONTEND COMPILED SUCCESSFULLY
echo   Output directory: %~dp0frontend\dist
echo   Run server with : start.bat or uv run server
echo ================================================================
endlocal
