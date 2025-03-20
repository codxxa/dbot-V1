
from flask import Flask, render_template, jsonify, request
from typing import Optional
import threading
from datetime import datetime

app = Flask(__name__)
bot_instance: Optional['DerivTradingBot'] = None
bot_thread: Optional[threading.Thread] = None
bot_running = False

def run_bot():
    global bot_instance, bot_running
    try:
        bot_instance.run()
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        bot_running = False

@app.route('/')
def home():
    return render_template('index.html', 
                         bot_running=bot_running,
                         stats=bot_instance.stats if bot_instance else None)

@app.route('/start', methods=['POST'])
def start_bot():
    global bot_instance, bot_thread, bot_running
    if not bot_running:
        from src.trading_bot import DerivTradingBot
        bot_instance = DerivTradingBot()
        bot_thread = threading.Thread(target=run_bot)
        bot_running = True
        bot_thread.start()
        return jsonify({"status": "success", "message": "Bot started"})
    return jsonify({"status": "error", "message": "Bot already running"})

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot_instance, bot_running
    if bot_running and bot_instance:
        bot_instance.handle_exit(None, None)
        bot_running = False
        return jsonify({"status": "success", "message": "Bot stopped"})
    return jsonify({"status": "error", "message": "Bot not running"})

@app.route('/stats')
def get_stats():
    if bot_instance:
        stats_dict = {}
        for symbol, stats in bot_instance.stats.items():
            stats_dict[symbol] = {
                "trades_placed": stats.trades_placed,
                "successful_trades": stats.successful_trades,
                "total_profit_loss": stats.total_profit_loss,
                "success_rate": stats.success_rate,
                "avg_profit_per_trade": stats.avg_profit_per_trade
            }
        return jsonify(stats_dict)
    return jsonify({})
