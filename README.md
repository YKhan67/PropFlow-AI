# PropFlow AI - FX Trading Infrastructure

High-performance automated FX trading infrastructure designed for professional traders and prop-firm participants.

## Features
- **MT5 Bridge:** Robust integration with MetaTrader 5, including a mock fallback for non-Windows environments.
- **Execution Engine:** Multi-pair market data handling and rule-based trade execution.
- **Risk Compliance Module:** Bulletproof risk management enforcing daily drawdown limits, total drawdown limits, and maximum position sizes.

## Project Structure
- `backend/app/broker/`: MT5 integration and mock broker.
- `backend/app/execution/`: Core execution engine and trade lifecycle management.
- `backend/app/services/`: Risk engine and other support services.
- `backend/app/main.py`: FastAPI entry point.
- `frontend/`: Web dashboard (to be implemented).
- `tests/`: Automated tests for system components.

## Getting Started
1. Install dependencies: `pip install -r requirements.txt`
2. Run the API: `python main.py` or `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`

## Risk Management
The `RiskManager` ensures all orders comply with strict prop-firm rules. It tracks:
- **Daily Drawdown:** Relative to the daily High Water Mark.
- **Total Drawdown:** Relative to the account High Water Mark.
- **Max Position Size:** Limits the volume of individual orders.
