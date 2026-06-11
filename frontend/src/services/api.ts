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
  regime?: string;
  pnl?: number;
}

export interface EquityHistoryPoint {
  timestamp: string;
  equity: number;
}

export interface HistoricalTrade {
  ticket: number;
  symbol: string;
  type: string;
  volume: number;
  profit: number;
  time: number;
  commission: number;
  swap: number;
  entry: number;
}

export interface SystemStatus {
  engine_running: boolean;
  account_name: string;
  account_number: number;
  balance: number;
  mt5_connected: boolean;
  mt5_error: string;
  risk_status: {
    starting_balance: number;
    current_equity: number;
    daily_drawdown: number;
    total_drawdown: number;
    max_daily_drawdown: number;
    max_total_drawdown: number;
    is_breached: boolean;
  };
  active_trades_count: number;
  market_regime: string;
  active_strategy: string;
  auto_zero_status: string;
  auto_zero_enabled: boolean;
  auto_zero_limit: number;
  aggressive_mode: boolean;
}

export interface RiskConfig {
  max_daily_drawdown: number;
  max_total_drawdown: number;
  max_position_size: number;
  account_balance: number;
  scale_down_excess: boolean;
  max_active_trades: number;
  global_take_profit: number;
  min_time_between_trades: number;
  active_strategy: "hybrid_hmm" | "quant_engine" | "correlation_reversion" | "gold_scalper";
  quant_zscore_entry?: number;
  quant_zscore_exit?: number;
  auto_zero_enabled?: boolean;
  auto_zero_loss_limit?: number;
  aggressive_mode?: boolean;
}

export interface AppConfig {
  risk: RiskConfig;
  symbols: string[]; // This will now represent symbols for HMM Strategy
  symbols_quant: string[]; // New field for Quant Strategy symbols
  timeframe?: string;
  mt5?: {
    login?: string;
    password?: string;
    server?: string;
  };
}

export const apiService = {
  async getStatus(): Promise<SystemStatus> {
    const response = await fetch(`${API_BASE_URL}/status`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch system status");
    return response.json();
  },

  async getConfig(): Promise<AppConfig> {
    const response = await fetch(`${API_BASE_URL}/config`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch config");
    return response.json();
  },

  async updateConfig(config: Partial<AppConfig>): Promise<AppConfig> {
    const response = await fetch(`${API_BASE_URL}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error("Failed to update config");
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

  async getSymbolHistory(symbol: string): Promise<{time: number, close: number}[]> {
    const response = await fetch(`${API_BASE_URL}/market/history/${symbol}`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch symbol history");
    return response.json();
  },

  async getAccountHistory(): Promise<EquityHistoryPoint[]> {
    const response = await fetch(`${API_BASE_URL}/account/history`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch account history");
    return response.json();
  },

  async getTradeHistory(days: number = 30): Promise<HistoricalTrade[]> {
    const response = await fetch(`${API_BASE_URL}/account/trade-history?days=${days}`, { cache: 'no-store' });
    if (!response.ok) throw new Error("Failed to fetch trade history");
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

  async closeAllTrades() {
    const response = await fetch(`${API_BASE_URL}/trades/close-all`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to close all trades");
    return response.json();
  },

  async closeProfitableTrades() {
    const response = await fetch(`${API_BASE_URL}/trades/close-profitable`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to close profitable trades");
    return response.json();
  },

  async zeroBuySellExposure(): Promise<{
    success: boolean;
    error?: string;
    offset_amount?: number;
    before?: { buy_pl: number; sell_pl: number; net_pl: number };
    after?: { buy_pl: number; sell_pl: number; net_pl: number };
  }> {
    const response = await fetch(`${API_BASE_URL}/trades/zero-exposure`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to zero exposure");
    return response.json();
  },

  async closeTrade(ticket: string | number) {
    const response = await fetch(`${API_BASE_URL}/trades/close/${ticket}`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to close trade");
    return response.json();
  },

  async runBacktest(params: {
    strategy: string;
    symbol: string;
    timeframe: string;
    date_from: string;
    date_to: string;
  }) {
    const response = await fetch(`${API_BASE_URL}/backtest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
    if (!response.ok) throw new Error("Failed to run backtest");
    return response.json();
  },
};
