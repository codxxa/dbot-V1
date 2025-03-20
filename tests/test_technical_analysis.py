"""Tests for technical analysis module"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.technical_analysis import TechnicalAnalysis
from src.exceptions import ValidationError

def test_calculate_indicators(sample_dataframe):
    """Test technical indicator calculations with added accuracy"""
    result = TechnicalAnalysis.calculate_indicators(sample_dataframe)

    # Check that all indicators are calculated
    assert 'SMA_5' in result.columns
    assert 'SMA_13' in result.columns  # Changed from SMA_20 to SMA_13
    assert 'RSI' in result.columns
    assert 'MACD' in result.columns
    assert 'BB_Upper' in result.columns
    assert 'ATR' in result.columns  # ATR for stop-loss adjustments
    assert 'EMA_9' in result.columns  # Added EMA for short-term trend detection
    assert 'ADX' in result.columns  # Added ADX for trend strength detection

    # Check indicator values are within expected ranges
    assert result['RSI'].min() >= 0
    assert result['RSI'].max() <= 100
    assert not result['SMA_5'].isna().all()
    assert not result['MACD'].isna().all()
    assert not result['ATR'].isna().all()  # ATR should be calculated
    assert result['ATR'].min() >= 0  # ATR should be positive
    assert result['ADX'].min() >= 0  # ADX should be positive
    assert result['ADX'].max() <= 100  # ADX should be within 0 to 100

def test_insufficient_data():
    """Test handling of insufficient data"""
    df = pd.DataFrame({
        'close': [100, 101],
        'open': [99, 100],
        'high': [102, 103],
        'low': [98, 99],
        'volume': [1000, 1100]
    })

    with pytest.raises(ValidationError):
        TechnicalAnalysis.calculate_indicators(df)

def test_detect_candlestick_patterns(sample_candles):
    """Test candlestick pattern detection"""
    patterns = TechnicalAnalysis.detect_candlestick_patterns(sample_candles[-3:])

    # Verify pattern detection returns correct format
    assert isinstance(patterns, list)
    for pattern in patterns:
        assert isinstance(pattern, tuple)
        assert len(pattern) == 2
        assert pattern[1] in ['bullish', 'bearish', 'neutral']

def test_get_trading_signal(sample_dataframe):
    """Test trading signal generation"""
    signal_result = TechnicalAnalysis.get_trading_signal(sample_dataframe)

    # Verify signal result properties
    assert signal_result.signal in ['CALL', 'PUT', 'NEUTRAL']
    assert isinstance(signal_result.reasons, list)
    assert 0 <= signal_result.strength <= 1
    assert isinstance(signal_result.timestamp, pd.Timestamp)

    # Verify stop-loss and take-profit are set when signals exist
    if signal_result.signal != 'NEUTRAL':
        assert signal_result.stop_loss is not None
        assert signal_result.take_profit is not None

def test_signal_strength():
    """Test signal strength calculation with improved trade filtering"""
    # Create data with strong bullish signals
    dates = pd.date_range(start='2025-01-01', periods=100, freq='1min')
    prices = []
    base_price = 100

    # Initial consolidation
    for i in range(20):
        prices.append(base_price * (1 + np.random.normal(0, 0.0002)))

    # Moderate decline to trigger oversold
    for i in range(30):
        base_price *= 0.997
        prices.append(base_price)

    # Brief consolidation at bottom
    bottom_price = base_price
    for i in range(20):
        prices.append(bottom_price * (1 + np.random.normal(0, 0.0002)))

    # Gentle recovery
    for i in range(30):
        base_price *= 1.002
        prices.append(base_price)

    prices = np.array(prices)
    noise = np.random.normal(0, 0.005, 100)  # Very small noise

    # Create DataFrame with clear bullish setup
    df = pd.DataFrame({
        'close': prices + noise,
        'open': prices + noise - 0.05,  # Tiny but consistent bullish candles
        'high': prices + noise + 0.1,
        'low': prices + noise - 0.1,
        'volume': np.random.normal(1000, 100, 100)
    }, index=dates)

    # Ensure proper high/low relationships
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)

    signal_result = TechnicalAnalysis.get_trading_signal(df)
    assert signal_result.signal == 'CALL'
    assert signal_result.strength > 0.7  # Increased minimum strength threshold
    assert signal_result.take_profit > signal_result.stop_loss  # For CALL trades

def test_vix_pairs():
    """Test multi-VIX support"""
    expected_pairs = [
        "R_10", "R_10_1S", "R_25", "R_25_1S", 
        "R_50", "R_50_1S", "R_75", "R_75_1S", 
        "R_100", "R_100_1S"
    ]
    assert all(pair in TechnicalAnalysis.VIX_PAIRS for pair in expected_pairs)

def test_atr_based_targets(sample_dataframe):
    """Test ATR-based stop-loss and take-profit calculations"""
    signal_result = TechnicalAnalysis.get_trading_signal(sample_dataframe)

    if signal_result.signal != 'NEUTRAL':
        last_close = sample_dataframe['close'].iloc[-1]
        last_atr = sample_dataframe['high'].iloc[-1] - sample_dataframe['low'].iloc[-1]

        if signal_result.signal == 'CALL':
            assert signal_result.stop_loss < last_close  # Stop-loss below current price
            assert signal_result.take_profit > last_close  # Take-profit above current price
            assert signal_result.take_profit - last_close > last_close - signal_result.stop_loss  # Risk:Reward > 1
        elif signal_result.signal == 'PUT':
            assert signal_result.stop_loss > last_close  # Stop-loss above current price 
            assert signal_result.take_profit < last_close  # Take-profit below current price
            assert last_close - signal_result.take_profit > signal_result.stop_loss - last_close  # Risk:Reward > 1

def test_ranging_market():
    """Test no trades are entered in a ranging market"""
    # Create data with ADX below 25 indicating a ranging market
    dates = pd.date_range(start='2025-01-01', periods=100, freq='1min')
    prices = np.random.normal(100, 0.5, 100)  # Prices fluctuating around 100
    df = pd.DataFrame({
        'close': prices,
        'open': prices - 0.1,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'volume': np.random.normal(1000, 100, 100)
    }, index=dates)

    # Add ADX column with values below 25
    df['TR'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['+DM'] = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']), df['high'] - df['high'].shift(), 0)
    df['-DM'] = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()), df['low'].shift() - df['low'], 0)
    df['+DI'] = 100 * (df['+DM'].ewm(alpha=1/14).mean() / df['ATR'])
    df['-DI'] = 100 * (df['-DM'].ewm(alpha=1/14).mean() / df['ATR'])
    df['DX'] = 100 * abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    df['ADX'] = df['DX'].ewm(alpha=1/14).mean()
    df['ADX'] = 20  # Set ADX to a constant value below 25

    signal_result = TechnicalAnalysis.get_trading_signal(df)
    assert signal_result.signal == 'NEUTRAL'
    assert "Market is ranging" in signal_result.reasons