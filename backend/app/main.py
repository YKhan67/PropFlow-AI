import json
import os
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.execution.execution_engine import ExecutionEngine
import logging

app = FastAPI(title="PropFlow AI Backend")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            'min_time_between_trades': 5
        },
        'symbols': ["EURUSD", "GBPUSD"],
        'timeframe': "H1"
    }

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Initial load
config_data = load_settings()
mt5_conf = config_data.get('mt5', {})
engine = ExecutionEngine(
    config_data['symbols'],
    config_data['risk'],
    mt5_login=mt5_conf.get('login'),
    mt5_password=mt5_conf.get('password'),
    mt5_server=mt5_conf.get('server'),
    timeframe=config_data.get('timeframe', 'H1')
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

        # Update AI Engine Signal Gate if it exists
        if engine.ai_engine:
            engine.ai_engine.signal_gate.dd_config.min_time_between_trades_minutes = config_data['risk'].get('min_time_between_trades', 5)
            engine.ai_engine.signal_gate.dd_config.daily_drawdown_limit_pct = config_data['risk'].get('max_daily_drawdown', 0.05) * 100
            engine.ai_engine.signal_gate.dd_config.total_drawdown_limit_pct = config_data['risk'].get('max_total_drawdown', 0.10) * 100
    if 'symbols' in new_config:
        config_data['symbols'] = new_config['symbols']
        engine.symbols = config_data['symbols']
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
            "market_regime": engine.get_market_regime()
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

@app.get("/market/scanner")
def get_market_scanner():
    return engine.get_market_scanner()

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
