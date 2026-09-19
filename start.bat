@echo off
echo ================================================================
echo   PERMITPROOF STAGE 2 ACCESS CONTROL SERVER
echo ================================================================
echo Starting backend server on http://localhost:8000 ...
echo Web Portal: http://localhost:8000/
echo Technician: http://localhost:8000/technician
echo Supervisor: http://localhost:8000/supervisor
echo Press Ctrl+C to stop the server.
echo ================================================================
uv run server
