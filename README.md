# Deriv Trading Bot

A robust, well-tested trading bot for the Deriv platform with comprehensive error handling and monitoring capabilities.

## Features

- Real-time market data analysis using WebSocket connection
- Multiple technical indicators (SMA, RSI, MACD, Bollinger Bands)
- Candlestick pattern recognition
- Comprehensive error handling and logging
- Automated trading based on configurable strategies
- Support for multiple trading symbols and timeframes

## Requirements

- Python 3.11 or higher
- Required Python packages (install via pip):
  - websockets
  - pandas
  - numpy
  - python-dotenv
  - pytest (for running tests)

## Setup

1. Clone or extract this repository
2. Install dependencies:
   ```bash
   pip install websockets pandas numpy python-dotenv pytest
   ```
3. Create a `.env` file in the root directory with your Deriv API key:
   ```
   DERIV_API_KEY=your_api_key_here
   ```
4. (Optional) Modify `config.json` to customize trading parameters:
   - Trading symbols
   - Stake amount
   - Duration
   - Trading hours
   - Analysis settings

## Configuration

The `config.json` file contains all trading parameters:

```json
{
    "symbols": ["R_10", "R_75", "R_100"],
    "trade_settings": {
        "stake": 1.0,
        "duration": 5,
        "duration_unit": "m"
    },
    "timeframes": ["1m", "5m", "15m"],
    "analysis_settings": {
        "min_signal_strength": 0.3,
        "lookback_periods": 100
    },
    "schedule": {
        "active_hours": {
            "start": "00:00",
            "end": "23:59"
        },
        "trade_interval": 300
    }
}
```

## Running the Bot

```bash
python main.py
```

The bot will:
1. Connect to Deriv's WebSocket API
2. Authenticate using your API key
3. Start monitoring specified symbols
4. Execute trades based on technical analysis
5. Log all activities to `deriv_bot.log`

## Testing

Run the test suite:
```bash
pytest tests/
```

## Logging

All bot activities are logged to `deriv_bot.log` with detailed information about:
- API connections
- Technical analysis results
- Trade executions
- Errors and warnings

## Error Handling

The bot includes comprehensive error handling for:
- API connection issues
- Authentication failures
- Data validation errors
- Trade execution failures

## Directory Structure

```
├── main.py                 # Main entry point
├── config.json            # Configuration file
├── .env                   # Environment variables
├── README.md             # This file
├── src/
│   ├── __init__.py
│   ├── api_client.py     # Deriv API client
│   ├── config.py         # Configuration management
│   ├── exceptions.py     # Custom exceptions
│   ├── models.py         # Data models
│   ├── technical_analysis.py  # Technical indicators
│   └── trading_bot.py    # Main bot logic
└── tests/                # Test suite
    ├── __init__.py
    ├── conftest.py
    ├── test_api_client.py
    ├── test_technical_analysis.py
    └── test_trading_bot.py
```

## Future Features

- Advanced technical indicators
- Machine learning predictions
- Automated backtesting
- Real-time performance dashboard

## Important Notes

- Always test with small stakes first
- Monitor the bot regularly
- Keep your API key secure
- Understand the risks of automated trading
- Regularly check the logs for any issues

## Support

For issues or questions:
1. Check the logs in `deriv_bot.log`
2. Review the error handling section
3. Contact Deriv support for API-related issues