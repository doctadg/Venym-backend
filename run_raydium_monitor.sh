#!/bin/bash
set -e

# Navigate to the backend directory
cd backend

# Activate virtual environment
source ../venv/bin/activate

# Run the Raydium monitor
python -m raydium_monitor.websocket_monitor

# Deactivate virtual environment
deactivate
