"""Tests for trading bot module"""
import pytest
from datetime import datetime, timedelta
from src.trading_bot import DerivTradingBot
from src.exceptions import ConfigError
from src.models import Trade, TradingStats

def test_bot_initialization():
    """Test bot initialization"""
    with pytest.raises(ConfigError):
        DerivTradingBot("nonexistent_config.json")

def test_analyze_symbol(mock_api, sample_dataframe):
    """Test symbol analysis"""
    bot = DerivTradingBot()
    bot.api = mock_api
    
    trade = bot.analyze_symbol("R_10")
    assert isinstance(trade, (Trade, type(None)))
    
    if trade:
        assert trade.symbol == "R_10"
        assert trade.contract_type in ["CALL", "PUT"]
        assert trade.status == "pending"

def test_execute_trade(mock_api, sample_trade):
    """Test trade execution"""
    bot = DerivTradingBot()
    bot.api = mock_api
    
    success = bot.execute_trade(sample_trade)
    assert success
    
    # Verify stats update
    assert bot.stats[sample_trade.symbol].trades_placed == 1
    assert sample_trade.status == "executed"

def test_trading_time_check():
    """Test trading time validation"""
    bot = DerivTradingBot()
    
    # Test during trading hours
    bot.config.config["schedule"]["active_hours"] = {
        "start": "00:00",
        "end": "23:59"
    }
    assert bot.is_trading_time()
    
    # Test outside trading hours
    bot.config.config["schedule"]["active_hours"] = {
        "start": "00:00",
        "end": "00:01"
    }
    if datetime.now().time() > datetime.strptime("00:01", "%H:%M").time():
        assert not bot.is_trading_time()

def test_performance_tracking(mock_api):
    """Test performance statistics tracking"""
    bot = DerivTradingBot()
    bot.api = mock_api
    
    # Add some test data
    stats = TradingStats(symbol="R_10")
    stats.trades_placed = 10
    stats.successful_trades = 7
    stats.calls = 6
    stats.puts = 4
    stats.total_profit_loss = 15.5
    
    bot.stats["R_10"] = stats
    
    # Verify stats calculation
    assert bot.stats["R_10"].success_rate == 70.0
    assert bot.stats["R_10"].total_profit_loss == 15.5
