"""Main trading bot implementation"""
import logging
import time
from typing import Dict, Optional
from datetime import datetime
import signal
import sys
from .config import Config
from .api_client import DerivAPI
from .technical_analysis import TechnicalAnalysis
from .models import Trade, TradingStats
from .exceptions import DerivBotError, APIError, ConfigError

logger = logging.getLogger(__name__)

class DerivTradingBot:
    """Main Trading Bot class"""

    def __init__(self, config_path: str = "config.json"):
        """Initialize the trading bot"""
        try:
            # Load configuration
            self.config = Config(config_path)

            # Initialize API client
            api_key = self.config.get("api_key")
            if not api_key:
                raise ConfigError("API key not found in configuration")
            self.api = DerivAPI(api_key)

            # Initialize performance tracking
            self.stats: Dict[str, TradingStats] = {
                symbol: TradingStats(symbol=symbol)
                for symbol in self.config.get("symbols", [])
            }

            # Track last trade times
            self.last_trade_time: Dict[str, datetime] = {
                symbol: datetime.min
                for symbol in self.config.get("symbols", [])
            }

            #Initialize active trades list
            self.active_trades = []

            # Set up signal handlers
            signal.signal(signal.SIGINT, self.handle_exit)
            signal.signal(signal.SIGTERM, self.handle_exit)

            # Get initial account balance
            try:
                balance = self.api.loop.run_until_complete(self.api.get_account_balance())
                logger.info(f"Initial account balance: ${balance:.2f}")
            except Exception as e:
                logger.error(f"Failed to get initial balance: {e}")
                balance = 0.0

            self.initial_balance = balance
            self.start_time = datetime.now()
            logger.info("Trading bot initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize trading bot: {e}")
            raise

    def calculate_stake(self, symbol: str, signal_strength: float) -> float:
        """Calculate trade stake based on balance and signal strength"""
        try:
            # Get current balance
            balance = self.api.loop.run_until_complete(self.api.get_account_balance())

            # Base stake from config
            base_stake = self.config.get("trade_settings", {}).get("stake", 1.0)

            # Calculate risk percentage (0.5% - 2% based on signal strength)
            risk_percent = min(2.0, max(0.5, signal_strength * 2))

            # Calculate maximum stake based on balance
            max_stake = balance * (risk_percent / 100)

            # Use the minimum of base stake and max stake
            stake = min(base_stake, max_stake)

            logger.info(f"Stake calculation for {symbol}:")
            logger.info(f"  Balance: ${balance:.2f}")
            logger.info(f"  Signal Strength: {signal_strength:.2f}")
            logger.info(f"  Risk %: {risk_percent:.1f}%")
            logger.info(f"  Calculated Stake: ${stake:.2f}")

            return round(stake, 2)

        except Exception as e:
            logger.error(f"Error calculating stake: {e}")
            return self.config.get("trade_settings", {}).get("stake", 1.0)

    def analyze_symbol(self, symbol: str) -> Optional[Trade]:
        """Analyze a symbol and create trade if conditions are met"""
        try:
            timeframes = self.config.get("timeframes", ["1m", "5m", "15m"])
            signals = []

            logger.info(f"Starting analysis for {symbol} across timeframes: {timeframes}")

            for tf in timeframes:
                df = self.api.fetch_historical_data(symbol, timeframe=tf)
                if df is not None and not df.empty:
                    signal_result = TechnicalAnalysis.get_trading_signal(df)
                    signals.append(signal_result)
                    logger.info(f"{symbol} {tf} analysis: {signal_result.signal} ({', '.join(signal_result.reasons)})")

            if not signals:
                logger.warning(f"No signals generated for {symbol}")
                return None

            # Count signals of each type
            call_signals = sum(1 for s in signals if s.signal == "CALL")
            put_signals = sum(1 for s in signals if s.signal == "PUT")

            # Calculate average signal strength
            avg_strength = sum(s.strength for s in signals) / len(signals)

            # Log signal summary
            logger.info(f"{symbol} signal summary: CALL={call_signals}, PUT={put_signals}, NEUTRAL={len(signals)-call_signals-put_signals}")
            logger.info(f"Average signal strength: {avg_strength:.2f}")

            # Calculate stake based on signal strength
            stake = self.calculate_stake(symbol, avg_strength)

            # Create trade if there's a clear signal
            if call_signals > put_signals and call_signals > len(signals) / 2:
                logger.info(f"Creating CALL trade for {symbol} based on {call_signals}/{len(signals)} signals")
                # Take the stop-loss and take-profit from the strongest signal
                strongest_signal = max(signals, key=lambda s: s.strength if s.signal == "CALL" else 0)
                trade = Trade(
                    symbol=symbol,
                    contract_type="CALL",
                    stake=stake,
                    duration=self.config.get("trade_settings", {}).get("duration", 5),
                    duration_unit=self.config.get("trade_settings", {}).get("duration_unit", "m"),
                    entry_time=datetime.now(),
                    signals=[f"{s.signal}: {', '.join(s.reasons)}" for s in signals],
                    stop_loss=strongest_signal.stop_loss,
                    take_profit=strongest_signal.take_profit
                )
                return trade
            elif put_signals > call_signals and put_signals > len(signals) / 2:
                logger.info(f"Creating PUT trade for {symbol} based on {put_signals}/{len(signals)} signals")
                # Take the stop-loss and take-profit from the strongest signal
                strongest_signal = max(signals, key=lambda s: s.strength if s.signal == "PUT" else 0)
                trade = Trade(
                    symbol=symbol,
                    contract_type="PUT",
                    stake=stake,
                    duration=self.config.get("trade_settings", {}).get("duration", 5),
                    duration_unit=self.config.get("trade_settings", {}).get("duration_unit", "m"),
                    entry_time=datetime.now(),
                    signals=[f"{s.signal}: {', '.join(s.reasons)}" for s in signals],
                    stop_loss=strongest_signal.stop_loss,
                    take_profit=strongest_signal.take_profit
                )
                return trade

            logger.info(f"No clear trading signal for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    def execute_trade(self, trade: Trade) -> bool:
        """Execute a trade and update statistics"""
        try:
            # Check current balance before trade
            try:
                current_balance = self.api.loop.run_until_complete(self.api.get_account_balance())
                logger.info(f"Current balance before trade: ${current_balance:.2f}")
                if current_balance < trade.stake:
                    logger.error(f"Insufficient balance (${current_balance:.2f}) for trade stake (${trade.stake:.2f})")
                    return False
            except Exception as e:
                logger.error(f"Failed to check balance before trade: {e}")
                return False

            response, success = self.api.place_trade(trade)

            if success:
                self.stats[trade.symbol].trades_placed += 1
                if trade.contract_type == "CALL":
                    self.stats[trade.symbol].calls += 1
                else:
                    self.stats[trade.symbol].puts += 1

                if response and 'buy' in response:
                    trade.contract_id = response['buy'].get('contract_id')
                    trade.status = "executed"
                    trade.entry_tick = float(response['buy'].get('entry_tick', 0))
                    self.active_trades.append(trade)
                    logger.info(f"Trade executed successfully: {trade}")
                    logger.info(f"Contract ID: {trade.contract_id}")
                    return True

            logger.warning(f"Trade execution failed: {trade}")
            if response:
                logger.debug(f"Failed trade response: {response}")
            return False

        except APIError as e:
            logger.error(f"API error executing trade: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error executing trade: {e}")
            return False

    def log_performance(self) -> None:
        """Log performance statistics with enhanced risk metrics"""
        try:
            current_balance = self.api.loop.run_until_complete(self.api.get_account_balance())
            total_pl = current_balance - self.initial_balance

            # Calculate time-based metrics
            now = datetime.now()
            session_duration = now - self.start_time

            logger.info("\n=== PERFORMANCE STATISTICS ===")
            logger.info(f"Session Duration: {session_duration.total_seconds() / 3600:.1f} hours")
            logger.info(f"Initial Balance: ${self.initial_balance:.2f}")
            logger.info(f"Current Balance: ${current_balance:.2f}")
            logger.info(f"Total P/L: ${total_pl:.2f} ({(total_pl/self.initial_balance * 100):.2f}%)")

            # Log enhanced statistics by symbol
            for symbol, stats in self.stats.items():
                trades = stats.trades_placed
                if trades > 0:
                    success_rate = stats.success_rate
                    call_ratio = (stats.calls / trades) * 100
                    put_ratio = (stats.puts / trades) * 100
                    avg_profit = stats.avg_profit_per_trade
                    risk_reward = abs(stats.best_trade / stats.worst_trade) if stats.worst_trade else 0

                    logger.info(f"\n{symbol} Statistics:")
                    logger.info(f"  Total Trades: {trades}")
                    logger.info(f"  Success Rate: {success_rate:.2f}%")
                    logger.info(f"  CALL/PUT Ratio: {call_ratio:.1f}%/{put_ratio:.1f}%")
                    logger.info(f"  Risk/Reward Ratio: {risk_reward:.2f}")
                    logger.info(f"  Average P/L per Trade: ${avg_profit:.2f}")
                    logger.info(f"  Best Trade: ${stats.best_trade:.2f}" if stats.best_trade is not None else "  Best Trade: N/A")
                    logger.info(f"  Worst Trade: ${stats.worst_trade:.2f}" if stats.worst_trade is not None else "  Worst Trade: N/A")
                    logger.info(f"  Current Win Streak: {stats.current_win_streak}")
                    logger.info(f"  Longest Win Streak: {stats.longest_win_streak}")
                else:
                    logger.info(f"\n{symbol}: No trades placed")

            logger.info("\n=== RISK MANAGEMENT SETTINGS ===")
            logger.info(f"Active Symbols: {', '.join(self.config.get('symbols', []))}")
            logger.info(f"Trade Settings:")
            logger.info(f"  Base Stake: ${self.config.get('trade_settings', {}).get('stake', 0):.2f}")
            logger.info(f"  Max Risk %: {self.config.get('trade_settings', {}).get('max_risk_percent', 0):.1f}%")
            logger.info(f"  Min Risk %: {self.config.get('trade_settings', {}).get('min_risk_percent', 0):.1f}%")
            logger.info(f"  Duration: {self.config.get('trade_settings', {}).get('duration', 0)} {self.config.get('trade_settings', {}).get('duration_unit', 'm')}")
            logger.info("\n============================\n")

        except Exception as e:
            logger.error(f"Failed to log performance statistics: {e}")

    def is_trading_time(self) -> bool:
        """Check if current time is within active trading hours"""
        schedule = self.config.get("schedule", {}).get("active_hours", {})
        now = datetime.now().time()

        start_time = datetime.strptime(schedule["start"], "%H:%M").time()
        end_time = datetime.strptime(schedule["end"], "%H:%M").time()

        if end_time < start_time:
            return now >= start_time or now <= end_time
        return start_time <= now <= end_time

    def run(self) -> None:
        """Main bot execution loop"""
        logger.info("Starting trading bot...")

        try:
            while True:
                if not self.is_trading_time():
                    logger.info("Outside trading hours, waiting...")
                    time.sleep(60)
                    continue

                current_time = datetime.now()
                trade_interval = self.config.get("schedule", {}).get("trade_interval", 300)

                # Update trade outcomes
                self.update_trade_outcomes()

                for symbol in self.config.get("symbols", []):
                    try:
                        time_since_last = (current_time - self.last_trade_time[symbol]).total_seconds()

                        if time_since_last >= trade_interval:
                            logger.info(f"Analyzing {symbol}...")
                            trade = self.analyze_symbol(symbol)

                            if trade:
                                if self.execute_trade(trade):
                                    self.last_trade_time[symbol] = current_time
                                else:
                                    logger.info(f"No trade opportunity for {symbol}")
                            else:
                                logger.info(f"No trade opportunity for {symbol}")
                        else:
                            remaining = trade_interval - time_since_last
                            logger.debug(f"Waiting {remaining:.0f}s for next {symbol} analysis")

                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue

                # Log performance periodically
                if current_time.minute % 10 == 0 and current_time.second < 10:
                    self.log_performance()

                time.sleep(10)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.handle_exit(None, None)
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.handle_exit(None, None)

    def handle_exit(self, signum, frame) -> None:
        """Handle graceful shutdown"""
        logger.info("Shutting down bot...")
        self.log_performance()
        logger.info("Bot stopped")
        sys.exit(0)

    def update_trade_outcomes(self):
        """Update statistics for completed trades"""
        try:
            for symbol, stats in self.stats.items():
                # Get all active trades
                active_trades = [t for t in self.active_trades if t.symbol == symbol and t.status == "executed"]

                for trade in active_trades:
                    try:
                        logger.info(f"Checking status for trade {trade.contract_id}")
                        update = self.api.loop.run_until_complete(
                            self.api.get_contract_update(trade.contract_id)
                        )

                        if update.get('is_sold', False):
                            profit = update['profit']
                            entry_tick = update['entry_tick']
                            exit_tick = update['exit_tick']
                            trade.profit_loss = profit
                            trade.result = "win" if profit > 0 else "loss"
                            trade.status = "completed"
                            trade.entry_tick = entry_tick
                            trade.exit_tick = exit_tick
                            trade.exit_time = datetime.now()

                            # Update statistics
                            if profit > 0:
                                stats.successful_trades += 1
                            stats.total_profit_loss += profit
                            stats.update_stats(trade)

                            logger.info(f"Trade completed - {trade.symbol} {trade.contract_type}:")
                            logger.info(f"  Entry: {trade.entry_tick:.5f}")
                            logger.info(f"  Exit: {trade.exit_tick:.5f}")
                            logger.info(f"  P/L: ${profit:.2f} ({trade.calculate_roi():.1f}%)")
                            logger.info(f"  Signals: {', '.join(trade.signals)}")

                            self.active_trades.remove(trade)
                        else:
                            logger.debug(f"Trade {trade.contract_id} still active, current status: {update.get('status', 'unknown')}")

                    except Exception as e:
                        logger.error(f"Error updating trade {trade.contract_id}: {e}")
                        # If we get subscription errors, mark the trade as completed
                        if "Input validation failed: subscribe" in str(e):
                            trade.status = "completed"
                            self.active_trades.remove(trade)
                            logger.warning(f"Removed trade {trade.contract_id} due to subscription error")
                        continue

        except Exception as e:
            logger.error(f"Error in update_trade_outcomes: {e}")