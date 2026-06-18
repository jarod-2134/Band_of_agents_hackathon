@echo off
cd /d "%~dp0"

:menu
cd /d "%~dp0"
cls
echo ==========================================
echo Band AI Control Plane
echo ==========================================
echo.
echo Please select an option:
echo 1. Start Backend (Python FastAPI)
echo 2. Start Frontend (React/Vite)
echo 3. Start Both Concurrently
echo 4. Setup Both (Install dependencies)
echo 5. Exit
echo.
set /p choice="Enter choice (1-5): "

if "%choice%"=="1" goto start_backend
if "%choice%"=="2" goto start_frontend
if "%choice%"=="3" goto start_both
if "%choice%"=="4" goto setup
if "%choice%"=="5" goto end
goto menu

:setup
echo.
echo Setting up Backend...
cd /d "%~dp0backend"
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
echo Installing Python dependencies...
pip install -r requirements.txt
cd /d "%~dp0"

echo.
echo Setting up Frontend...
cd /d "%~dp0frontend"
echo Installing npm dependencies...
call npm install
cd /d "%~dp0"

echo.
echo Setup complete!
pause
goto menu

:start_backend
echo.
echo Starting Backend Server...
echo Press Ctrl+C to stop.
cd /d "%~dp0backend"
if not exist "venv\" (
    echo Virtual environment not found! Please run setup first.
    cd /d "%~dp0"
    pause
    goto menu
)
call venv\Scripts\activate
python main.py
cd /d "%~dp0"
pause
goto menu

:start_frontend
echo.
echo Starting Frontend Server...
echo Press Ctrl+C to stop.
cd /d "%~dp0frontend"
if not exist "node_modules\" (
    echo node_modules not found! Running npm install...
    call npm install
)
call npm run dev
cd /d "%~dp0"
pause
goto menu

:start_both
echo.
echo Starting both servers concurrently...
echo Press Ctrl+C to stop both servers.
cd /d "%~dp0"
npx concurrently -k -n "BACKEND,FRONTEND" -c "blue,green" "cd backend && venv\Scripts\activate && python main.py" "cd frontend && npm run dev"
pause
goto menu

:end
