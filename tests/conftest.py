"""Test fixtures and configuration"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.models import Candle, Trade
from src.api_client import DerivAPI

@pytest.fixture
def sample_candles():
    """Generate sample candle data"""
    now = datetime.now()
    candles = []
    base_price = 100.0
    
    for i in range(100):
        timestamp = now - timedelta(minutes=i)
        open_price = base_price + np.random.normal(0, 0.1)
        close_price = open_price + np.random.normal(0, 0.1)
        high_price = max(open_price, close_price) + abs(np.random.normal(0, 0.05))
        low_price = min(open_price, close_price) - abs(np.random.normal(0, 0.05))
        
        candles.append(Candle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=abs(np.random.normal(1000, 200))
        ))
    
    return candles

@pytest.fixture
def sample_dataframe():
    """Generate sample DataFrame for technical analysis"""
    now = datetime.now()
    dates = [now - timedelta(minutes=i) for i in range(100)]
    
    data = {
        'timestamp': dates,
        'open': np.random.normal(100, 1, 100),
        'high': np.random.normal(101, 1, 100),
        'low': np.random.normal(99, 1, 100),
        'close': np.random.normal(100, 1, 100),
        'volume': np.abs(np.random.normal(1000, 200, 100))
    }
    
    # Ensure high/low prices are consistent
    for i in range(len(data['high'])):
        data['high'][i] = max(data['open'][i], data['close'][i], data['high'][i])
        data['low'][i] = min(data['open'][i], data['close'][i], data['low'][i])
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df

@pytest.fixture
def sample_trade():
    """Generate sample trade object"""
    return Trade(
        symbol="R_10",
        contract_type="CALL",
        stake=1.0,
        duration=5,
        duration_unit="m",
        entry_time=datetime.now()
    )

@pytest.fixture
def mock_api():
    """Create a mock API client"""
    class MockDerivAPI(DerivAPI):
        def __init__(self):
            self.api_key = "test_key"
            self.calls = []
        
        def _make_request(self, url, payload, timeout=10):
            self.calls.append((url, payload))
            return {"candles": [], "buy": {"contract_id": "test_123"}}
    
    return MockDerivAPI()
