"""Technical analysis implementation with enhanced multi-VIX support and optimized strategy"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from datetime import datetime
from .models import SignalResult, Candle
from .exceptions import ValidationError

class TechnicalAnalysis:
    """Technical analysis methods for multiple VIX pairs"""

    VIX_PAIRS = ["R_10", "R_10_1S", "R_25", "R_25_1S", "R_50", "R_50_1S", "R_75", "R_75_1S", "R_100", "R_100_1S"]

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators for multiple VIX pairs"""
        if len(df) < 50:
            raise ValidationError("Insufficient data for technical analysis")

        data = df.copy()

        # Moving Averages - Adjusted windows for faster response
        data['SMA_5'] = data['close'].rolling(window=5).mean()
        data['SMA_13'] = data['close'].rolling(window=13).mean()  # Changed from 20 to 13
        data['SMA_50'] = data['close'].rolling(window=50).mean()
        data['EMA_9'] = data['close'].ewm(span=9, adjust=False).mean()

        # RSI with standard settings
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # MACD with faster settings
        data['EMA_12'] = data['close'].ewm(span=12, adjust=False).mean()
        data['EMA_26'] = data['close'].ewm(span=26, adjust=False).mean()
        data['MACD'] = data['EMA_12'] - data['EMA_26']
        data['MACD_Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['MACD_Histogram'] = data['MACD'] - data['MACD_Signal']

        # Bollinger Bands with standard deviation adjustments
        data['BB_Middle'] = data['close'].rolling(window=20).mean()
        data['BB_Std'] = data['close'].rolling(window=20).std()
        data['BB_Upper'] = data['BB_Middle'] + 2.2 * data['BB_Std']  # Slightly wider bands
        data['BB_Lower'] = data['BB_Middle'] - 2.2 * data['BB_Std']

        # ATR for Stop-Loss & Take-Profit Strategy
        data['ATR'] = data['high'] - data['low']
        data['ATR'] = data['ATR'].rolling(14).mean()

        # Additional Indicator: Stochastic Oscillator
        data['L14'] = data['low'].rolling(window=14).min()
        data['H14'] = data['high'].rolling(window=14).max()
        data['%K'] = 100 * ((data['close'] - data['L14']) / (data['H14'] - data['L14']))
        data['%D'] = data['%K'].rolling(window=3).mean()

        # Additional Indicator: ADX for trend strength
        data['TR'] = np.maximum(data['high'] - data['low'], np.maximum(abs(data['high'] - data['close'].shift()), abs(data['low'] - data['close'].shift())))
        data['ATR'] = data['TR'].rolling(window=14).mean()
        data['+DM'] = np.where((data['high'] - data['high'].shift()) > (data['low'].shift() - data['low']), data['high'] - data['high'].shift(), 0)
        data['-DM'] = np.where((data['low'].shift() - data['low']) > (data['high'] - data['high'].shift()), data['low'].shift() - data['low'], 0)
        data['+DI'] = 100 * (data['+DM'].ewm(alpha=1/14).mean() / data['ATR'])
        data['-DI'] = 100 * (data['-DM'].ewm(alpha=1/14).mean() / data['ATR'])
        data['DX'] = 100 * abs(data['+DI'] - data['-DI']) / (data['+DI'] + data['-DI'])
        data['ADX'] = data['DX'].ewm(alpha=1/14).mean()

        return data

    @staticmethod
    def detect_candlestick_patterns(candles: List[Candle]) -> List[Tuple[str, str]]:
        """Detect candlestick patterns"""
        if len(candles) < 3:
            return []

        patterns = []
        last = candles[-1]
        prev = candles[-2]
        third = candles[-3]

        # Bullish Engulfing
        if (last.close > last.open and 
            prev.close < prev.open and
            last.open < prev.close and 
            last.close > prev.open):
            patterns.append(('Bullish Engulfing', 'bullish'))

        # Bearish Engulfing
        if (last.close < last.open and 
            prev.close > prev.open and
            last.open > prev.close and 
            last.close < prev.open):
            patterns.append(('Bearish Engulfing', 'bearish'))

        # Hammer
        if (last.close > last.open and
            (last.high - last.close) < (last.open - last.low) * 0.3 and
            (last.close - last.open) < (last.open - last.low) * 0.3 and
            (last.open - last.low) > (last.close - last.open) * 2):
            patterns.append(('Hammer', 'bullish'))

        # Shooting Star
        if (last.close < last.open and
            (last.high - last.open) > (last.close - last.low) * 2 and
            (last.open - last.close) < (last.high - last.open) * 0.3):
            patterns.append(('Shooting Star', 'bearish'))

        # Doji
        if abs(last.close - last.open) < (last.high - last.low) * 0.1:
            patterns.append(('Doji', 'neutral'))

        return patterns

    @staticmethod
    def get_trading_signal(df: pd.DataFrame) -> SignalResult:
        """Determine trading signal based on enhanced strategy"""
        if len(df) < 50:
            return SignalResult(
                signal="NEUTRAL",
                reasons=["Insufficient data"],
                strength=0.0,
                timestamp=pd.Timestamp(datetime.now()),
                stop_loss=None,
                take_profit=None
            )

        data = TechnicalAnalysis.calculate_indicators(df)
        latest = data.iloc[-1]
        previous = data.iloc[-2]

        # Check for ranging market on 15-minute chart
        if data['ADX'].iloc[-1] < 25:
            return SignalResult(
                signal="NEUTRAL",
                reasons=["Market is ranging"],
                strength=0.0,
                timestamp=pd.Timestamp(datetime.now()),
                stop_loss=None,
                take_profit=None
            )

        signals = []
        reasons = []
        signal_weights = []

        # Check for strong trend reversal (highest priority)
        recent_low_idx = df['close'][-20:].idxmin()
        recent_high_idx = df['close'][-20:].idxmax()
        recent_low = df['close'][recent_low_idx]
        recent_high = df['close'][recent_high_idx]

        if latest['close'] > recent_low * 1.005 and latest['RSI'] < 45:
            signals.append(1)
            reasons.append("Potential bullish reversal")
            signal_weights.append(3.5)  # Increased weight for reversals
        elif latest['close'] < recent_high * 0.995 and latest['RSI'] > 55:
            signals.append(-1)
            reasons.append("Potential bearish reversal")
            signal_weights.append(3.5)

        # RSI Confirmation (high priority)
        if latest['RSI'] < 35:  # Adjusted from 30
            signals.append(1)
            reasons.append(f"RSI oversold ({latest['RSI']:.2f})")
            signal_weights.append(3.0)
        elif latest['RSI'] > 65:  # Adjusted from 70
            signals.append(-1)
            reasons.append(f"RSI overbought ({latest['RSI']:.2f})")
            signal_weights.append(3.0)

        # Moving Average Crossovers (high priority)
        if latest['SMA_5'] > latest['SMA_13'] and previous['SMA_5'] <= previous['SMA_13']:
            signals.append(1)
            reasons.append("Fast MA crossed above medium MA")
            signal_weights.append(2.5)
        elif latest['SMA_5'] < latest['SMA_13'] and previous['SMA_5'] >= previous['SMA_13']:
            signals.append(-1)
            reasons.append("Fast MA crossed below medium MA")
            signal_weights.append(2.5)

        # Trend Strength
        if latest['SMA_5'] > latest['SMA_50']:
            signals.append(1)
            reasons.append("Above long-term MA")
            signal_weights.append(1.5)
        elif latest['SMA_5'] < latest['SMA_50']:
            signals.append(-1)
            reasons.append("Below long-term MA")
            signal_weights.append(1.5)

        # MACD Confirmation (medium priority)
        if latest['MACD'] > latest['MACD_Signal'] and previous['MACD'] <= previous['MACD_Signal']:
            signals.append(1)
            reasons.append("MACD crossed above signal")
            signal_weights.append(2.0)
        elif latest['MACD'] < latest['MACD_Signal'] and previous['MACD'] >= previous['MACD_Signal']:
            signals.append(-1)
            reasons.append("MACD crossed below signal")
            signal_weights.append(2.0)

        # Bollinger Bands (lower priority)
        if latest['close'] < latest['BB_Lower']:
            signals.append(1)
            reasons.append("Price below lower band")
            signal_weights.append(1.0)
        elif latest['close'] > latest['BB_Upper']:
            signals.append(-1)
            reasons.append("Price above upper band")
            signal_weights.append(1.0)

        # Stochastic Oscillator Confirmation (medium priority)
        if latest['%K'] < 20 and latest['%D'] < 20 and latest['%K'] > latest['%D']:
            signals.append(1)
            reasons.append("Stochastic Oscillator indicates oversold")
            signal_weights.append(2.0)
        elif latest['%K'] > 80 and latest['%D'] > 80 and latest['%K'] < latest['%D']:
            signals.append(-1)
            reasons.append("Stochastic Oscillator indicates overbought")
            signal_weights.append(2.0)

        # Early exit if no signals
        if not signals:
            return SignalResult(
                signal="NEUTRAL",
                reasons=["No strong confirmation"],
                strength=0.0,
                timestamp=pd.Timestamp(datetime.now()),
                stop_loss=None,
                take_profit=None
            )

        # Calculate stop-loss and take-profit levels with adjusted ATR multipliers
        base_price = latest['close']
        atr_multiplier_sl = 1.2  # Reduced from 1.5 for tighter stops
        atr_multiplier_tp = 2.5  # Reduced from 3.0 for more realistic targets

        if signals[0] == 1:  # CALL
            stop_loss = base_price - (latest['ATR'] * atr_multiplier_sl)
            take_profit = base_price + (latest['ATR'] * atr_multiplier_tp)
        else:  # PUT
            stop_loss = base_price + (latest['ATR'] * atr_multiplier_sl)
            take_profit = base_price - (latest['ATR'] * atr_multiplier_tp)

        # Calculate weighted signal with adjusted thresholds
        weighted_sum = sum(s * w for s, w in zip(signals, signal_weights))
        total_weight = sum(signal_weights)
        avg_signal = weighted_sum / total_weight

        strength = abs(avg_signal)
        # More balanced thresholds
        if avg_signal > 0.18:  # Lowered from 0.2
            signal = "CALL"
        elif avg_signal < -0.18:  # Lowered from -0.2
            signal = "PUT"
        else:
            signal = "NEUTRAL"

        return SignalResult(
            signal=signal,
            reasons=reasons,
            strength=strength,
            timestamp=pd.Timestamp(datetime.now()),
            stop_loss=stop_loss,
            take_profit=take_profit
        )