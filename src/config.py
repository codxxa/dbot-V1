"""Configuration management module"""
import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
from .exceptions import ConfigError

@dataclass
class TradeSettings:
    """Trade settings configuration"""
    stake: float
    duration: int
    duration_unit: str
    max_risk_percent: float = field(default=2.0)
    min_risk_percent: float = field(default=0.5)

    def validate(self) -> None:
        """Validate trade settings"""
        if self.stake <= 0:
            raise ConfigError("Stake must be positive")
        if self.duration <= 0:
            raise ConfigError("Duration must be positive")
        if self.duration_unit not in ['m', 'h', 'd']:
            raise ConfigError("Invalid duration unit")
        if self.max_risk_percent <= 0 or self.max_risk_percent > 5:
            raise ConfigError("Max risk percent must be between 0 and 5")
        if self.min_risk_percent <= 0 or self.min_risk_percent >= self.max_risk_percent:
            raise ConfigError("Min risk percent must be positive and less than max risk percent")

@dataclass
class ScheduleSettings:
    """Schedule settings configuration"""
    active_hours_start: str
    active_hours_end: str
    trade_interval: int

    def validate(self) -> None:
        """Validate schedule settings"""
        try:
            datetime.strptime(self.active_hours_start, "%H:%M")
            datetime.strptime(self.active_hours_end, "%H:%M")
        except ValueError:
            raise ConfigError("Invalid time format in schedule")
        if self.trade_interval <= 0:
            raise ConfigError("Trade interval must be positive")

class Config:
    """Configuration manager"""

    def __init__(self, config_path: str = "config.json"):
        """Initialize configuration"""
        self.config_path = config_path
        self.api_key = os.getenv("DERIV_API_KEY")
        if not self.api_key:
            raise ConfigError("DERIV_API_KEY environment variable not set")
        self.config: Dict[str, Any] = self._load_config()
        self.validate()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = self._create_default_config()
            config["api_key"] = self.api_key
            return config
        except json.JSONDecodeError:
            raise ConfigError("Invalid JSON in config file")

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        config = {
            "symbols": ["R_10", "R_75", "R_100"],
            "trade_settings": {
                "stake": 1.0,
                "duration": 5,
                "duration_unit": "m",
                "max_risk_percent": 2.0,
                "min_risk_percent": 0.5
            },
            "timeframes": ["1m", "5m", "15m"],
            "analysis_settings": {
                "min_signal_strength": 0.3,
                "lookback_periods": 100,
                "rsi_thresholds": {
                    "oversold": 30,
                    "overbought": 70
                }
            },
            "schedule": {
                "active_hours": {
                    "start": "00:00",
                    "end": "23:59"
                },
                "trade_interval": 300
            }
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=4)
        return config

    def validate(self) -> None:
        """Validate configuration"""
        if not self.config.get("symbols"):
            raise ConfigError("No trading symbols configured")

        # Extract trade settings with defaults
        trade_settings_data = self.config.get("trade_settings", {})
        trade_settings = TradeSettings(
            stake=trade_settings_data.get("stake", 1.0),
            duration=trade_settings_data.get("duration", 5),
            duration_unit=trade_settings_data.get("duration_unit", "m"),
            max_risk_percent=trade_settings_data.get("max_risk_percent", 2.0),
            min_risk_percent=trade_settings_data.get("min_risk_percent", 0.5)
        )
        trade_settings.validate()

        schedule = ScheduleSettings(
            active_hours_start=self.config["schedule"]["active_hours"]["start"],
            active_hours_end=self.config["schedule"]["active_hours"]["end"],
            trade_interval=self.config["schedule"]["trade_interval"]
        )
        schedule.validate()

        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        for tf in self.config["timeframes"]:
            if tf not in valid_timeframes:
                raise ConfigError(f"Invalid timeframe: {tf}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def save(self) -> None:
        """Save configuration to file"""
        save_config = self.config.copy()
        save_config.pop("api_key", None)
        with open(self.config_path, 'w') as f:
            json.dump(save_config, f, indent=4)

logger = logging.getLogger(__name__)