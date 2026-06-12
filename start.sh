#!/bin/bash

# Get the directory where this script is located (equivalent to %~dp0)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_menu() {
    cd "$SCRIPT_DIR" || exit
    clear
    echo "=========================================="
    echo "Band AI Control Plane (Ubuntu)"
    echo "=========================================="
    echo ""
    echo "Please select an option:"
    echo "1. Start Backend (Python FastAPI)"
    echo "2. Start Frontend (React/Vite)"
    echo "3. Start Both Concurrently"
    echo "4. Setup Both (Install dependencies)"
    echo "5. Exit"
    echo ""
    read -p "Enter choice (1-5): " choice

    case $choice in
        1) start_backend ;;
        2) start_frontend ;;
        3) start_both ;;
        4) setup_env ;;
        5) exit 0 ;;
        *) show_menu ;;
    esac
}

pause_and_menu() {
    echo ""
    read -p "Press [Enter] key to return to menu..." temp
    show_menu
}

setup_env() {
    echo ""
    echo "Setting up Backend..."
    cd "$SCRIPT_DIR/backend" || exit
    
    # Check for python3.13 specifically based on your latest setup
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment using python3.13..."
        python3.13 -m venv .venv
    fi
    
    # Linux path uses bin/activate instead of Scripts/activate
    source .venv/bin/activate
    echo "Installing Python dependencies..."
    pip install fastapi uvicorn websockets asyncpg sentence-transformers
    deactivate
    
    echo ""
    echo "Setting up Frontend..."
    cd "$SCRIPT_DIR/frontend" || exit
    echo "Installing npm dependencies..."
    npm install
    
    echo ""
    echo "Setup complete!"
    pause_and_menu
}

start_backend() {
    echo ""
    echo "Starting Backend Server..."
    echo "Press Ctrl+C to stop."
    cd "$SCRIPT_DIR/backend" || exit
    
    if [ ! -d ".venv" ]; then
        echo "Virtual environment (.venv) not found! Please run setup first."
        pause_and_menu
    fi
    
    source .venv/bin/activate
    python main.py
    pause_and_menu
}

start_frontend() {
    echo ""
    echo "Starting Frontend Server..."
    echo "Press Ctrl+C to stop."
    cd "$SCRIPT_DIR/frontend" || exit
    
    if [ ! -d "node_modules" ]; then
        echo "node_modules not found! Running npm install..."
        npm install
    fi
    
    npm run dev
    pause_and_menu
}

start_both() {
    echo ""
    echo "Starting both servers concurrently..."
    echo "Press Ctrl+C to stop both servers."
    cd "$SCRIPT_DIR" || exit
    
    # Uses Ubuntu syntax for concurrent execution matching your paths
    npx concurrently -k -n "BACKEND,FRONTEND" -c "blue,green" \
        "cd backend && source .venv/bin/activate && python main.py" \
        "cd frontend && npm run dev"
        
    pause_and_menu
}

# Kick off the menu loop
show_menu