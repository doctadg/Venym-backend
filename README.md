# Raydium AMM Pool Monitor

## Overview
This project monitors Raydium AMM pools in real-time, extracting transaction details, fetching token information, and storing data in Redis.

## Prerequisites
- Python 3.8+
- Virtual environment support

## Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file with the following variables:
```
HELIUS_WSS_ENDPOINT=wss://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY
HELIUS_API_KEY=YOUR_HELIUS_API_KEY
RAYDIUM_AMM_PROGRAM_ID=675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8
UPSTASH_ENDPOINT=your-upstash-endpoint
UPSTASH_PASSWORD=your-upstash-password
UPSTASH_PORT=6379
```

### 5. Run the Monitor
```bash
./run_raydium_monitor.sh
```

## Logging
Detailed logs are available at `backend/raydium_monitor.log`

## Components
- `websocket_monitor.py`: Main monitoring script
- `run_raydium_monitor.sh`: Execution script with virtual environment management

## Workflow
1. Connect to Helius WebSocket
2. Subscribe to Raydium AMM program transactions
3. Extract transaction signatures
4. Fetch full transaction details
5. Extract token addresses
6. Retrieve token information from DexScreener
7. Store data in Upstash Redis

## Troubleshooting
- Ensure all environment variables are correctly set
- Check `backend/raydium_monitor.log` for detailed error messages
- Verify network connectivity to Helius RPC and DexScreener API
