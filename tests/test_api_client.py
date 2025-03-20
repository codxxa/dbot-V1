"""Tests for API client module"""
import pytest
import pandas as pd
from datetime import datetime
from src.api_client import DerivAPI
from src.exceptions import APIError

def test_fetch_historical_data(mock_api, sample_dataframe):
    """Test historical data fetching"""
    df = mock_api.fetch_historical_data("R_10", timeframe="1m", count=100)
    
    # Verify DataFrame structure
    assert isinstance(df, pd.DataFrame)
    assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
    assert isinstance(df.index, pd.DatetimeIndex)

def test_invalid_timeframe(mock_api):
    """Test handling of invalid timeframe"""
    with pytest.raises(ValueError):
        mock_api.fetch_historical_data("R_10", timeframe="invalid")

def test_place_trade(mock_api, sample_trade):
    """Test trade placement"""
    response, success = mock_api.place_trade(sample_trade)
    
    # Verify API call
    assert len(mock_api.calls) == 1
    assert mock_api.calls[0][1]["parameters"]["symbol"] == sample_trade.symbol
    assert mock_api.calls[0][1]["parameters"]["contract_type"] == sample_trade.contract_type
    
    # Verify response handling
    assert success
    assert "contract_id" in response["buy"]

def test_api_error_handling(mock_api):
    """Test API error handling"""
    def raise_error(*args, **kwargs):
        raise Exception("API Error")
    
    mock_api._make_request = raise_error
    
    with pytest.raises(APIError):
        mock_api.fetch_historical_data("R_10")
