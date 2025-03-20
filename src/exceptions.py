"""Custom exceptions for the trading bot"""

class DerivBotError(Exception):
    """Base exception for all bot errors"""
    pass

class APIError(DerivBotError):
    """Raised when API calls fail"""
    pass

class ConfigError(DerivBotError):
    """Raised for configuration issues"""
    pass

class ValidationError(DerivBotError):
    """Raised for data validation errors"""
    pass

class TradingError(DerivBotError):
    """Raised for trading operation errors"""
    pass
