"""Data models for the trading bot"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class Trade:
    """Represents a single trade"""
    symbol: str
    contract_type: str
    stake: float
    duration: int
    duration_unit: str
    entry_time: datetime
    contract_id: Optional[str] = None
    status: str = "pending"
    result: Optional[str] = None
    profit_loss: Optional[float] = None
    entry_tick: Optional[float] = None
    exit_tick: Optional[float] = None
    exit_time: Optional[datetime] = None
    signals: List[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def calculate_roi(self) -> float:
        """Calculate ROI for the trade"""
        if self.profit_loss is not None and self.stake > 0:
            return (self.profit_loss / self.stake) * 100
        return 0.0

@dataclass
class TradingStats:
    """Trading statistics for a symbol"""
    symbol: str
    trades_placed: int = 0
    successful_trades: int = 0
    calls: int = 0
    puts: int = 0
    total_profit_loss: float = 0.0
    best_trade: Optional[float] = None
    worst_trade: Optional[float] = None
    longest_win_streak: int = 0
    current_win_streak: int = 0
    avg_profit_per_trade: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        return (self.successful_trades / self.trades_placed * 100) if self.trades_placed > 0 else 0

    def update_stats(self, trade: Trade) -> None:
        """Update statistics with completed trade"""
        if trade.profit_loss is not None:
            if self.best_trade is None or trade.profit_loss > self.best_trade:
                self.best_trade = trade.profit_loss
            if self.worst_trade is None or trade.profit_loss < self.worst_trade:
                self.worst_trade = trade.profit_loss
            if trade.profit_loss > 0:
                self.current_win_streak += 1
                self.longest_win_streak = max(self.longest_win_streak, self.current_win_streak)
            else:
                self.current_win_streak = 0
            self.avg_profit_per_trade = self.total_profit_loss / self.trades_placed if self.trades_placed > 0 else 0

@dataclass
class SignalResult:
    """Technical analysis signal result"""
    signal: str
    reasons: List[str]
    strength: float
    timestamp: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def __post_init__(self):
        if self.signal not in ["CALL", "PUT", "NEUTRAL"]:
            raise ValueError("Invalid signal type")

@dataclass
class Candle:
    """Candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def is_bullish(self) -> bool:
        """Check if candle is bullish"""
        return self.close > self.open

    def is_bearish(self) -> bool:
        """Check if candle is bearish"""
        return self.close < self.open

    def body_size(self) -> float:
        """Calculate candle body size"""
        return abs(self.close - self.open)

    def upper_shadow(self) -> float:
        """Calculate upper shadow length"""
        return self.high - max(self.open, self.close)

    def lower_shadow(self) -> float:
        """Calculate lower shadow length"""
        return min(self.open, self.close) - self.low