"""Main entry point for the trading bot"""
import os
import sys
import logging
from dotenv import load_dotenv
from src.trading_bot import DerivTradingBot
from src.exceptions import DerivBotError, ConfigError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deriv_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up environment variables and validate requirements"""
    # Load environment variables
    load_dotenv()

    # Check for required environment variables
    if not os.getenv("DERIV_API_KEY"):
        logger.error("DERIV_API_KEY not found in environment variables")
        sys.exit(1)

def main():
    """Main function"""
    try:
        # Set up environment
        setup_environment()

        # Initialize and run bot with enhanced features
        logger.info("Initializing trading bot with enhanced strategy...")
        bot = DerivTradingBot()
        logger.info("Starting bot with multi-VIX support and optimized risk management...")
        bot.run()

    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except DerivBotError as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()