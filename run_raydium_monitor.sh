#!/bin/bash
set -e

# Navigate to the backend directory
cd backend

# Activate virtual environment
source ../venv/bin/activate

# Install requirements from the root directory
pip3 install -r ../requirements.txt

# Run the Raydium monitor
python3 -m raydium_monitor.websocket_monitor

# Deactivate virtual environment
deactivate
