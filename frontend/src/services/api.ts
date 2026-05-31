const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AccountMetrics {
  equity: number;
  balance: number;
  drawdown: number;
  daily_pnl: number;
  total_trades: number;
  win_rate: number;
}

export interface Trade {
  id: string;
  symbol: string;
  type: string;
  volume: number;
  profit: number;
  open_price: number;
  current_price: number;
  open_time: string;
}

export interface MarketSymbol {
  symbol: string;
  bid: number;
  ask: number;
  change: number;
  trend: "up" | "down";
}

export interface EquityHistoryPoint {
  timestamp: string;
  equity: number;
}

export interface SystemStatus {
  engine_running: boolean;
  health: string;
  account_metrics: AccountMetrics;
  active_trade_count: number;
}

export const apiService = {
  async getStatus(): Promise<SystemStatus> {
    const response = await fetch(`${API_BASE_URL}/status`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch system status");
    return response.json();
  },

  async getActiveTrades(): Promise<Trade[]> {
    const response = await fetch(`${API_BASE_URL}/trades/active`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch active trades");
    return response.json();
  },

  async getMarketScanner(): Promise<MarketSymbol[]> {
    const response = await fetch(`${API_BASE_URL}/market/scanner`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch market scanner");
    return response.json();
  },

  async getAccountHistory(): Promise<EquityHistoryPoint[]> {
    const response = await fetch(`${API_BASE_URL}/account/history`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch account history");
    return response.json();
  },

  async startEngine() {
    const response = await fetch(`${API_BASE_URL}/engine/start`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to start engine");
    return response.json();
  },

  async stopEngine() {
    const response = await fetch(`${API_BASE_URL}/engine/stop`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to stop engine");
    return response.json();
  },
};
