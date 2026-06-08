import json
import os
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.execution.execution_engine import ExecutionEngine
from app.execution.backtest_engine import BacktestEngine
import logging
from datetime import datetime

# Configure logging to show engine activity in the console
logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Ensure third party logs don't drown out our engine
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("PropFlow-AI")

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {
        'risk': {
            'max_daily_drawdown': 0.05,
            'max_total_drawdown': 0.10,
            'max_position_size': 0.5,
            'account_balance': 100000.0,
            'scale_down_excess': True,
            'max_active_trades': 5,
            'global_take_profit': 0.0,
            'min_time_between_trades': 5,
            'active_strategy': "hybrid_hmm",
            'quant_zscore_entry': 2.0,
            'quant_zscore_exit': 0.5,
            'correlation_threshold': 0.8
        },
        'symbols': ["EURUSD", "GBPUSD"],
        'symbols_quant': ["EURUSD", "GBPUSD", "USDJPY"],
        'symbols_corr': ["EURUSD", "GBPUSD", "USDCHF", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD"],
        'symbols_gold': ["XAUUSD"],
        'timeframe': "H1"
    }

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Initial config load for routes
config_data = load_settings()

# Engine will be initialized in lifespan
engine: ExecutionEngine = None
backtest_engine: BacktestEngine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, backtest_engine

    mt5_conf = config_data.get('mt5', {})
    active_strategy = config_data['risk'].get('active_strategy', 'hybrid_hmm')

    # Select correct symbols based on saved strategy
    if active_strategy == 'hybrid_hmm':
        initial_symbols = config_data.get('symbols', [])
    elif active_strategy == 'quant_engine':
        initial_symbols = config_data.get('symbols_quant', [])
    elif active_strategy == 'correlation_reversion':
        initial_symbols = config_data.get('symbols_corr', [])
    else:
        initial_symbols = config_data.get('symbols_gold', [])

    logger.info("Initializing PropFlow AI Engine...")
    engine = ExecutionEngine(
        initial_symbols,
        config_data['risk'],
        mt5_login=mt5_conf.get('login'),
        mt5_password=mt5_conf.get('password'),
        mt5_server=mt5_conf.get('server'),
        timeframe=config_data.get('timeframe', 'H1')
    )
    backtest_engine = BacktestEngine(engine.bridge)

    yield

    if engine:
        logger.info("Initiating engine shutdown...")
        engine.shutdown()

    logger.info("FastAPI lifespan shutdown complete. Forcing process termination...")
    # The nuclear option for Windows to ensure all threads and child processes are killed
    os._exit(0)

app = FastAPI(title="PropFlow AI Backend", lifespan=lifespan)

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "PropFlow AI API is running"}

@app.get("/config")
def get_config():
    return config_data

@app.post("/config")
def update_config(new_config: dict):
    global config_data
    if 'risk' in new_config:
        config_data['risk'].update(new_config['risk'])
        engine.risk_manager.config.update(config_data['risk'])
        engine.risk_manager.starting_balance = config_data['risk'].get('account_balance', 100000.0)

        # Update AI Engines if they exist
        if hasattr(engine, 'hmm_handler'):
            engine.hmm_handler.ai.signal_gate.dd_config.min_time_between_trades_seconds = config_data['risk'].get('min_time_between_trades', 300)
            engine.hmm_handler.ai.signal_gate.dd_config.daily_drawdown_limit_pct = config_data['risk'].get('max_daily_drawdown', 0.05) * 100
            engine.hmm_handler.ai.signal_gate.dd_config.total_drawdown_limit_pct = config_data['risk'].get('max_total_drawdown', 0.10) * 100
        if hasattr(engine, 'quant_handler'):
            engine.quant_handler.ai.z_entry = config_data['risk'].get('quant_zscore_entry', 2.0)
            engine.quant_handler.ai.z_exit = config_data['risk'].get('quant_zscore_exit', 0.5)

        # Switch engine active symbols based on strategy change
        if config_data['risk'].get('active_strategy') == 'hybrid_hmm':
            engine.symbols = config_data['symbols']
        elif config_data['risk'].get('active_strategy') == 'quant_engine':
            engine.symbols = config_data.get('symbols_quant', [])
        elif config_data['risk'].get('active_strategy') == 'correlation_reversion':
            engine.symbols = config_data.get('symbols_corr', [])
        else:
            engine.symbols = config_data.get('symbols_gold', [])
    if 'symbols' in new_config:
        config_data['symbols'] = new_config['symbols']
        # engine.symbols is used as the active trading list
        if config_data['risk'].get('active_strategy') == 'hybrid_hmm':
            engine.symbols = config_data['symbols']
    if 'symbols_quant' in new_config:
        config_data['symbols_quant'] = new_config['symbols_quant']
        if config_data['risk'].get('active_strategy') == 'quant_engine':
            engine.symbols = config_data['symbols_quant']
    if 'symbols_corr' in new_config:
        config_data['symbols_corr'] = new_config['symbols_corr']
        if config_data['risk'].get('active_strategy') == 'correlation_reversion':
            engine.symbols = config_data['symbols_corr']
    if 'symbols_gold' in new_config:
        config_data['symbols_gold'] = new_config['symbols_gold']
        if config_data['risk'].get('active_strategy') == 'gold_scalper':
            engine.symbols = config_data['symbols_gold']
    if 'timeframe' in new_config:
        config_data['timeframe'] = new_config['timeframe']
        engine.set_timeframe(config_data['timeframe'])
    if 'mt5' in new_config:
        config_data.setdefault('mt5', {}).update(new_config['mt5'])
        engine.bridge.login = config_data['mt5'].get('login')
        engine.bridge.password = config_data['mt5'].get('password')
        engine.bridge.server = config_data['mt5'].get('server')
        # Re-initialize bridge with new credentials
        engine.bridge.initialize()

    save_settings(config_data)
    return {"message": "Configuration updated successfully", "config": config_data}

@app.get("/status")
def get_status():
    try:
        risk = engine.risk_manager.get_status()
        acc = engine.get_account_info()
        return {
            "engine_running": engine.running,
            "account_name": acc.get("name") or "Unknown",
            "account_number": acc.get("login", 0),
            "balance": acc.get("balance", 0),
            "mt5_connected": acc.get("connected", False),
            "mt5_error": acc.get("error", ""),
            "risk_status": {
                "starting_balance": engine.risk_manager.starting_balance,
                "current_equity": risk["equity"],
                "daily_drawdown": risk["daily_drawdown"] * 100,
                "total_drawdown": risk["total_drawdown"] * 100,
                "max_daily_drawdown": config_data['risk']['max_daily_drawdown'] * 100,
                "max_total_drawdown": config_data['risk']['max_total_drawdown'] * 100,
                "is_breached": risk["total_drawdown"] >= config_data['risk']['max_total_drawdown']
            },
            "active_trades_count": len(engine.get_active_trades()),
            "market_regime": engine.get_market_regime(),
            "active_strategy": config_data['risk'].get('active_strategy', 'hybrid_hmm')
        }
    except Exception as e:
        logging.error(f"Status error: {e}")
        return {"error": str(e)}

@app.get("/trades/active")
def get_active_trades():
    return engine.get_active_trades()

@app.post("/trades/close-all")
def close_all_trades():
    success = engine.close_all_trades()
    return {"message": "Close all trades initiated", "success": success}

@app.post("/trades/close/{ticket}")
def close_trade(ticket: int):
    success = engine.bridge.close_position(ticket)
    return {"message": f"Close trade {ticket} initiated", "success": success}

@app.post("/backtest")
def run_backtest(params: dict):
    try:
        strategy = params.get('strategy')
        symbol = params.get('symbol')
        timeframe = params.get('timeframe')
        lot_size = params.get('lot_size', 0.1)
        profit_target = params.get('profit_target', 0)
        date_from = datetime.fromisoformat(params.get('date_from').replace('Z', ''))
        date_to = datetime.fromisoformat(params.get('date_to').replace('Z', ''))

        result = backtest_engine.run_backtest(
            strategy, symbol, timeframe, date_from, date_to, config_data['risk'], lot_size, profit_target
        )
        return result
    except Exception as e:
        logging.error(f"Backtest error: {e}")
        return {"error": str(e)}

@app.get("/market/scanner")
def get_market_scanner():
    return engine.get_market_scanner()

@app.get("/market/history/{symbol}")
def get_market_history(symbol: str):
    # Check if we have high-res 5s data in the engine buffer
    with engine.data_lock:
        if symbol in engine.price_history_5s and len(engine.price_history_5s[symbol]) > 0:
            return engine.price_history_5s[symbol]

    # Fallback to MT5 if buffer is empty
    logging.info(f"Fetching market history from MT5: {symbol}")
    data = engine.bridge.get_market_data(symbol, count=100)
    if data is not None:
        import pandas as pd
        df = pd.DataFrame.from_records(data)
        return df[['time', 'close']].to_dict('records')
    return []

@app.get("/account/history")
def get_equity_history():
    return engine.get_equity_history()

@app.get("/account/trade-history")
def get_trade_history(days: int = 30):
    return engine.bridge.get_trade_history(days=days)

@app.post("/engine/start")
def start_engine(background_tasks: BackgroundTasks):
    if not engine.running:
        background_tasks.add_task(engine.start)
        return {"message": "Execution Engine start initiated"}
    return {"message": "Execution Engine is already running"}

@app.post("/engine/stop")
def stop_engine():
    if engine.running:
        engine.stop()
        return {"message": "Execution Engine stopped"}
    return {"message": "Execution Engine is not running"}
