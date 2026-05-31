from fastapi import FastAPI, BackgroundTasks
from app.execution.execution_engine import ExecutionEngine
import logging

app = FastAPI(title="PropFlow AI Backend")

# Configuration (Placeholder, should ideally come from env or db)
risk_config = {
    'max_daily_drawdown': 0.05,
    'max_total_drawdown': 0.10,
    'max_position_size': 0.5,
    'account_balance': 100000.0,
    'scale_down_excess': True
}
symbols = ["EURUSD", "GBPUSD"]

engine = ExecutionEngine(symbols, risk_config)

@app.get("/")
def read_root():
    return {"message": "PropFlow AI API is running"}

@app.get("/status")
def get_status():
    return {
        "engine_running": engine.running,
        "risk_status": engine.risk_manager.get_status(),
        "active_trades_count": len(engine.get_active_trades()),
        "market_regime": engine.get_market_regime()
    }

@app.get("/trades/active")
def get_active_trades():
    return engine.get_active_trades()

@app.get("/market/scanner")
def get_market_scanner():
    return engine.get_market_scanner()

@app.get("/account/history")
def get_equity_history():
    return engine.get_equity_history()

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
