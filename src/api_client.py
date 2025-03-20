"""Deriv API client implementation"""
import json
import time
import logging
import pandas as pd
import websockets
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from .exceptions import APIError
from .models import Trade

logger = logging.getLogger(__name__)

class DerivAPI:
    """Client for interacting with Deriv API via WebSocket"""

    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.ws_url = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
        self.websocket = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.connected = False
        self.last_ping = 0

    async def connect(self, force_reconnect=False):
        """Establish WebSocket connection"""
        try:
            if force_reconnect and self.websocket:
                await self.websocket.close()
                self.websocket = None
                self.connected = False

            if not self.websocket or not self.connected:
                logger.info("Establishing WebSocket connection...")
                self.websocket = await websockets.connect(self.ws_url)

                # Authenticate
                auth_request = {"authorize": self.api_key}
                logger.info("Sending authorization request...")
                await self.websocket.send(json.dumps(auth_request))

                auth_response = await self.websocket.recv()
                auth_data = json.loads(auth_response)

                logger.debug(f"Authorization response: {json.dumps(auth_data, indent=2)}")

                if 'error' in auth_data:
                    error_msg = auth_data['error']['message']
                    logger.error(f"Authorization failed: {error_msg}")
                    raise APIError(f"Authorization failed: {error_msg}")

                if 'authorize' in auth_data:
                    logger.info("Successfully authorized with Deriv API")
                    self.connected = True
                    self.last_ping = time.time()
                else:
                    logger.error("Unexpected authorization response")
                    raise APIError("Failed to authorize with Deriv API")

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket connection error: {e}")
            self.connected = False
            raise APIError(f"WebSocket connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}")
            self.connected = False
            raise APIError(f"Connection failed: {str(e)}")

    async def send_request(self, request: Dict[str, Any], retry_count=0) -> Dict[str, Any]:
        """Send request and get response"""
        try:
            # Check connection health
            if not self.connected or time.time() - self.last_ping > 30:
                await self.connect(force_reconnect=True)

            request["req_id"] = str(int(time.time()))

            # Log request details
            logger.debug(f"Sending request: {json.dumps(request, indent=2)}")
            await self.websocket.send(json.dumps(request))

            response = await self.websocket.recv()
            response_data = json.loads(response)

            # Log full response for debugging
            logger.debug(f"Received response: {json.dumps(response_data, indent=2)}")

            if 'error' in response_data:
                error_msg = response_data['error']['message']
                logger.error(f"API error: {error_msg}")
                raise APIError(f"API error: {error_msg}")

            self.last_ping = time.time()
            return response_data

        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            logger.warning(f"WebSocket connection closed: {e}")
            self.connected = False

            if retry_count < self.MAX_RETRIES:
                logger.info(f"Retrying request (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(self.RETRY_DELAY)
                return await self.send_request(request, retry_count + 1)
            else:
                raise APIError("Max retries exceeded for request")

        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise APIError(f"Request failed: {str(e)}")

    async def get_account_balance(self) -> float:
        """Get current account balance"""
        try:
            response = await self.send_request({"balance": 1, "subscribe": 0})
            logger.debug(f"Balance response: {json.dumps(response, indent=2)}")

            if 'balance' in response:
                balance = float(response['balance'].get('balance', 0))
                currency = response['balance'].get('currency', 'USD')
                logger.info(f"Current balance: {balance} {currency}")
                return balance
            else:
                raise APIError("Balance information not found in response")

        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise APIError(f"Failed to get account balance: {str(e)}")

    def fetch_historical_data(self, symbol: str, timeframe: str = '1m', count: int = 100) -> pd.DataFrame:
        """Fetch historical candle data"""
        timeframe_map = {
            '1m': 60, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '4h': 14400, '1d': 86400
        }

        granularity = timeframe_map.get(timeframe)
        if not granularity:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        try:
            logger.info(f"Fetching historical data for {symbol}")
            end_time = int(time.time())
            start_time = end_time - (count * granularity)

            response = self.loop.run_until_complete(self.send_request({
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": end_time,
                "start": start_time,
                "granularity": granularity,
                "style": "candles"
            }))

            # Log the full response for debugging
            logger.debug(f"Historical data response: {json.dumps(response, indent=2)}")

            if 'candles' in response:
                candles = response['candles']
            elif 'history' in response and 'candles' in response['history']:
                candles = response['history']['candles']
            else:
                available_keys = list(response.keys())
                logger.error(f"Unexpected response structure. Available keys: {available_keys}")
                raise APIError("No historical data in response")

            if not candles:
                raise APIError("Empty candles data received")

            data = {
                'timestamp': [datetime.fromtimestamp(c['epoch']) for c in candles],
                'open': [float(c['open']) for c in candles],
                'high': [float(c['high']) for c in candles],
                'low': [float(c['low']) for c in candles],
                'close': [float(c['close']) for c in candles],
                'volume': [float(0) for _ in candles]  # Deriv doesn't provide volume
            }

            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)

            logger.info(f"Successfully fetched {len(df)} candles for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise APIError(f"Failed to fetch historical data: {str(e)}")

    def place_trade(self, trade: Trade) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Place a trade on Deriv"""
        try:
            # Check balance before trading
            balance = self.loop.run_until_complete(self.get_account_balance())
            if balance < trade.stake:
                logger.error(f"Insufficient balance ({balance}) for trade stake ({trade.stake})")
                return None, False

            logger.info(f"Placing {trade.contract_type} trade for {trade.symbol}")
            response = self.loop.run_until_complete(self.send_request({
                "buy": 1,
                "price": trade.stake,
                "parameters": {
                    "amount": trade.stake,
                    "basis": "stake",
                    "contract_type": trade.contract_type,
                    "currency": "USD",
                    "duration": trade.duration,
                    "duration_unit": trade.duration_unit,
                    "symbol": trade.symbol
                }
            }))

            if 'buy' in response:
                contract_id = response['buy'].get('contract_id', 'unknown')
                logger.info(f"Trade placed successfully: Contract ID {contract_id}")
                return response, True
            else:
                logger.warning(f"Unexpected response format: {response}")
                return None, False

        except Exception as e:
            logger.error(f"Error placing trade: {e}")
            raise APIError(f"Failed to place trade: {str(e)}")

    async def get_contract_update(self, contract_id: str) -> Dict[str, Any]:
        """Get contract updates"""
        try:
            response = await self.send_request({
                "proposal_open_contract": 1,
                "contract_id": contract_id,
                "subscribe": 1  # Changed from 0 to 1 to maintain subscription
            })

            logger.debug(f"Contract update response: {json.dumps(response, indent=2)}")

            if 'proposal_open_contract' in response:
                contract = response['proposal_open_contract']
                return {
                    'status': contract.get('status', 'unknown'),
                    'profit': float(contract.get('profit', 0)),
                    'entry_tick': float(contract.get('entry_tick', 0)),
                    'current_spot': float(contract.get('current_spot', 0)),
                    'exit_tick': float(contract.get('exit_tick', 0)) if contract.get('exit_tick') else None,
                    'is_sold': contract.get('is_sold', False)
                }
            else:
                raise APIError("Contract update information not found in response")

        except Exception as e:
            logger.error(f"Failed to get contract update: {e}")
            raise APIError(f"Failed to get contract update: {str(e)}")

    def __del__(self):
        """Cleanup WebSocket connection"""
        if self.websocket and self.loop and self.connected:
            try:
                self.loop.run_until_complete(self.websocket.close())
                self.connected = False
            except Exception as e:
                logger.error(f"Error closing WebSocket connection: {e}")