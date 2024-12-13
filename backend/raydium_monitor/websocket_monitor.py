import os
import pickle
import asyncio
import json
import logging
import random
import time
import requests
import redis
import base58
from dotenv import load_dotenv
from solana.rpc.async_api import AsyncClient
import websockets

# Load environment variables
load_dotenv()

# Ensure logs directory exists and create full path to log file
log_file_path = '/home/user/venym-ai-backend/backend/logs/raydium_monitor.log'
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file_path,
    filemode='a'
)
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

# Environment Variables
HELIUS_WSS_ENDPOINT = os.getenv('HELIUS_WSS_ENDPOINT')
HELIUS_API_KEY = os.getenv('HELIUS_API_KEY')
RAYDIUM_AMM_PROGRAM_ID = os.getenv('RAYDIUM_AMM_PROGRAM_ID')
UPSTASH_ENDPOINT = os.getenv('UPSTASH_ENDPOINT')
UPSTASH_PASSWORD = os.getenv('UPSTASH_PASSWORD')
UPSTASH_PORT = os.getenv('UPSTASH_PORT')

# Address tracking file
ADDRESS_TRACKING_FILE = '/home/user/venym-ai-backend/backend/raydium_monitor/tracked_addresses.pkl'

def load_tracked_addresses():
    """Load previously tracked addresses from a pickle file"""
    try:
        if os.path.exists(ADDRESS_TRACKING_FILE):
            with open(ADDRESS_TRACKING_FILE, 'rb') as f:
                return pickle.load(f)
        return set()
    except Exception as e:
        logger.error(f"Error loading tracked addresses: {e}")
        return set()

def save_tracked_addresses(addresses):
    """Save tracked addresses to a pickle file"""
    try:
        with open(ADDRESS_TRACKING_FILE, 'wb') as f:
            pickle.dump(addresses, f)
    except Exception as e:
        logger.error(f"Error saving tracked addresses: {e}")

def is_new_address(address, tracked_addresses):
    """Check if an address is new and not previously tracked"""
    return address not in tracked_addresses

def add_tracked_address(address, tracked_addresses):
    """Add a new address to the tracked set"""
    tracked_addresses.add(address)
    save_tracked_addresses(tracked_addresses)

def is_valid_solana_address(address):
    """Validate if a string is a valid Solana address"""
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except Exception:
        return False

def extract_token_addresses_from_transaction(transaction):
    """Comprehensive token address extraction from transaction details"""
    token_addresses = set()
    
    try:
        def extract_addresses(obj):
            if isinstance(obj, list):
                return [addr for addr in obj if is_valid_solana_address(addr)]
            elif isinstance(obj, dict):
                return [addr for addr in obj.values() if is_valid_solana_address(addr)]
            return []

        # Extract from various transaction components
        if transaction:
            components = [
                transaction.get('transaction', {}).get('message', {}).get('accountKeys', []),
                transaction.get('meta', {}).get('innerInstructions', []),
                transaction.get('transaction', {}).get('message', {})
            ]

            for component in components:
                addresses = extract_addresses(component)
                token_addresses.update(addresses)
    
    except Exception as e:
        logger.error(f"Comprehensive address extraction error: {e}")
    
    # Remove any invalid addresses
    token_addresses = {addr for addr in token_addresses if is_valid_solana_address(addr)}
    
    logger.info(f"Extracted {len(token_addresses)} valid token addresses")
    return list(token_addresses)

def fetch_transaction_details(transaction_id):
    """Fetch full transaction details from Helius"""
    try:
        url = f'https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}'
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                transaction_id, 
                {
                    "maxSupportedTransactionVersion": 0,
                    "commitment": "confirmed"
                }
            ]
        }
        
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        response_json = response.json()
        transaction_details = response_json.get('result')
        
        return transaction_details
    
    except requests.RequestException as e:
        logger.error(f"Error fetching transaction details: {e}")
        return None

def fetch_token_details(token_addresses):
    """Enhanced token details fetching with robust error handling"""
    tracked_addresses = load_tracked_addresses()
    
    new_addresses = [
        addr for addr in token_addresses 
        if is_new_address(addr, tracked_addresses)
    ]
    
    if not new_addresses:
        logger.info("No new token addresses to fetch")
        return []

    try:
        addresses_str = ','.join(new_addresses[:30])
        url = f'https://api.dexscreener.com/latest/dex/tokens/{addresses_str}'
        
        logger.info(f"Fetching token details for {len(new_addresses)} new addresses")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        token_data = response.json()
        
        # More robust data validation
        if not token_data or 'pairs' not in token_data or not isinstance(token_data['pairs'], list):
            logger.warning(f"Invalid or empty token data: {token_data}")
            return []
        
        # Filter out pairs with missing or invalid base token
        valid_pairs = [
            pair for pair in token_data['pairs'] 
            if pair.get('baseToken', {}).get('address')
        ]
        
        # Add newly processed addresses to tracked set
        for pair in valid_pairs:
            base_token_address = pair['baseToken']['address']
            add_tracked_address(base_token_address, tracked_addresses)
        
        return valid_pairs
    
    except requests.RequestException as e:
        logger.error(f"DexScreener API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in fetch_token_details: {e}")
        return []

def create_redis_client():
    """Create a Redis client for Upstash"""
    try:
        return redis.Redis(
            host=UPSTASH_ENDPOINT,
            port=int(UPSTASH_PORT or 6379),
            password=UPSTASH_PASSWORD,
            ssl=True
        )
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        return None

def store_token_data_in_redis(redis_client, transaction_signature, token_data):
    """Enhanced token data storage with more detailed logging"""
    if not redis_client or not token_data:
        logger.warning(f"Cannot store token data for {transaction_signature}: invalid Redis client or token data")
        return

    stored_tokens = 0
    for pair in token_data:
        try:
            base_token = pair.get('baseToken', {})
            base_token_address = base_token.get('address')
            
            if not base_token_address:
                logger.warning(f"No base token address found in pair for transaction {transaction_signature}")
                continue
            
            redis_key = f"token:{base_token_address}"
            
            # Include transaction signature in stored data for traceability
            pair_data = {
                **pair,
                'transaction_signature': transaction_signature
            }
            
            redis_client.set(
                redis_key, 
                json.dumps(pair_data),
                ex=86400  # Expire after 24 hours
            )
            
            stored_tokens += 1
            logger.info(f"Stored pair data for base token {base_token_address} from transaction {transaction_signature}")
        
        except Exception as e:
            logger.error(f"Failed to store pair data in Redis for transaction {transaction_signature}: {e}")
    
    logger.info(f"Stored {stored_tokens} token pairs from transaction {transaction_signature}")

async def keep_websocket_alive(websocket):
    """Periodically send ping to keep WebSocket connection alive"""
    try:
        while True:
            await websocket.ping()
            await asyncio.sleep(30)  # Send ping every 30 seconds
    except Exception as e:
        logger.error(f"WebSocket keep-alive error: {e}")

async def monitor_raydium_pools():
    """Monitor Raydium AMM pools and process new pool events"""
    redis_client = create_redis_client()
    
    max_reconnect_attempts = 10
    base_delay = 1  # Base delay for exponential backoff
    max_delay = 60  # Maximum delay between reconnection attempts
    max_total_connection_time = 3600  # 1 hour total connection attempt time
    start_time = time.time()

    for attempt in range(max_reconnect_attempts):
        # Check total connection attempt time
        if time.time() - start_time > max_total_connection_time:
            logger.critical("Total connection attempt time exceeded. Stopping reconnection attempts.")
            break

        try:
            # Calculate exponential backoff with jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, 0.1 * delay)
            reconnect_delay = delay + jitter

            logger.info(f"Attempting WebSocket connection (Attempt {attempt + 1})")
            logger.info(f"Reconnection delay: {reconnect_delay:.2f} seconds")

            async with websockets.connect(
                HELIUS_WSS_ENDPOINT, 
                extra_headers={"Authorization": f"Bearer {HELIUS_API_KEY}"},
                ping_interval=30,  # Send ping every 30 seconds
                ping_timeout=10    # Wait 10 seconds for pong response
            ) as websocket:
                logger.info("WebSocket connection established successfully")

                # Reset reconnection attempts on successful connection
                attempt = 0

                # Start keep-alive task
                keep_alive_task = asyncio.create_task(keep_websocket_alive(websocket))

                # Helius-specific WebSocket subscription for program logs
                subscribe_message = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "logsSubscribe",
                    "params": [{
                        "mentions": [RAYDIUM_AMM_PROGRAM_ID]
                    }, {
                        "commitment": "processed"
                    }]
                }

                await websocket.send(json.dumps(subscribe_message))
                logger.info("Sent Helius logs subscription request")

                while True:
                    try:
                        message = await websocket.recv()
                        logger.debug(f"Raw WebSocket message: {message}")
                        
                        # Robust parsing with multiple checks
                        try:
                            data = json.loads(message)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON message: {message}")
                            continue

                        # Validate message structure
                        if not isinstance(data, dict):
                            logger.warning(f"Unexpected message type: {type(data)}")
                            continue

                        # Check for logs subscription result
                        if 'method' in data and data['method'] == 'logsSubscribe':
                            logger.info("Received logs subscription confirmation")
                            continue

                        # Extract transaction details
                        result = data.get('params', {}).get('result', {})
                        if not result:
                            logger.warning("No result found in WebSocket message")
                            continue

                        transaction_signature = result.get('value', {}).get('signature')
                        
                        if not transaction_signature:
                            logger.warning("No transaction signature found in WebSocket message")
                            continue
                        
                        logger.info(f"Processing transaction: {transaction_signature}")
                        
                        # Fetch full transaction details
                        transaction_details = fetch_transaction_details(transaction_signature)
                        
                        if not transaction_details:
                            logger.warning(f"No transaction details found for {transaction_signature}")
                            continue
                        
                        # Extract token addresses
                        token_addresses = extract_token_addresses_from_transaction(transaction_details)
                        
                        if not token_addresses:
                            logger.warning(f"No token addresses found in transaction {transaction_signature}")
                            continue
                        
                        # Fetch token details
                        token_data = fetch_token_details(token_addresses)
                        
                        if not token_data:
                            logger.warning(f"No token data found for addresses in transaction {transaction_signature}")
                            continue
                        
                        # Store in Redis
                        if redis_client:
                            store_token_data_in_redis(redis_client, transaction_signature, token_data)
                        
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed unexpectedly")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket message processing error: {e}")
                        logger.error(f"Error details: {type(e)}")
                        # Add a small delay to prevent tight error loops
                        await asyncio.sleep(1)
                    
                    # Prevent potential tight loop
                    await asyncio.sleep(0.5)
                
                # Cancel keep-alive task if connection is lost
                keep_alive_task.cancel()
                try:
                    await keep_alive_task
                except asyncio.CancelledError:
                    pass

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket connection error (Attempt {attempt + 1}): {e}")
            await asyncio.sleep(reconnect_delay)
        
        except Exception as e:
            logger.critical(f"Unexpected error in WebSocket connection: {e}")
            break
    
    logger.critical("Max reconnection attempts reached. Exiting.")

async def main():
    """Main entry point for the Raydium pool monitor"""
    logger.info("Starting Raydium AMM Pool Monitor")
    try:
        await monitor_raydium_pools()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())
