#!/bin/bash
set -e

# Navigate to the backend directory
cd backend


# Activate virtual environment
source ../venv/bin/activate

pip3 install -r backend/requirements.txt

# Run the Raydium monitor
python3 -m raydium_monitor.websocket_monitor

# Deactivate virtual environment
deactivate
