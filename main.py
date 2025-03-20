"""Main entry point for the trading bot web interface"""
import os
import logging
from dotenv import load_dotenv
from src.web_interface import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("deriv_bot.log"),
        logging.StreamHandler()
    ]
)

def setup_environment():
    """Set up environment variables"""
    load_dotenv()
    if not os.getenv("DERIV_API_KEY"):
        logging.error("DERIV_API_KEY not found in environment variables")
        return False
    return True

if __name__ == "__main__":
    if setup_environment():
        app.run(host='0.0.0.0', port=8080, debug=False)