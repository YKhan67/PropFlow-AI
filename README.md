# PropFlow AI - FX Trading Infrastructure

High-performance automated FX trading infrastructure designed for professional traders and prop-firm participants.

## Features
- **AI Market Regime Detection:** Sophisticated HMM-based classification (Trending, Ranging, Volatile) to adapt strategy parameters in real-time.
- **MT5 Bridge:** Robust integration with MetaTrader 5, including a mock fallback for local development.
- **Execution Engine:** Multi-pair market data handling and hybrid AI + Rule-based trade execution.
- **Risk Compliance Module:** Bulletproof risk management enforcing daily drawdown limits, total drawdown limits, and maximum position sizes (Prop-firm compliant).
- **Monitoring Dashboard:** Real-time Next.js dashboard for performance tracking and system health monitoring.

## Project Structure
- `backend/`: FastAPI core application.
  - `app/broker/`: MT5 integration and mock broker.
  - `app/execution/`: Core execution engine and trade lifecycle management.
  - `app/services/`: Risk engine and other support services.
- `ai/`: Machine learning models and feature engineering.
  - `regime/`: HMM detector for market regimes.
  - `engine/`: Hybrid decision engine combining AI and rules.
- `frontend/`: Next.js monitoring dashboard.
- `scripts/`: Automation and orchestration scripts.
- `tests/`: Automated tests for system components.
- `docker-compose.yml`: Root orchestration for full-stack deployment.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (optional)

### Quick Start (Local)
1. Install backend dependencies: `pip install -r requirements.txt`
2. Install frontend dependencies: `cd frontend && npm install`
3. Run the full stack: `./scripts/start_all.sh`

### Docker Deployment
```bash
docker-compose up --build
```

## Risk Management
The `RiskManager` ensures all orders comply with strict prop-firm rules. It tracks:
- **Daily Drawdown:** Relative to the daily High Water Mark.
- **Total Drawdown:** Relative to the account High Water Mark.
- **Max Position Size:** Limits the volume of individual orders.
- **Regime-Aware Risk:** Automatically scales position sizes based on market volatility and regime confidence.
