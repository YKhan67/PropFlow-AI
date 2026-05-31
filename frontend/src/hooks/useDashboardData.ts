import { useState, useEffect } from 'react';
import { apiService, SystemStatus, Trade, MarketSymbol, EquityHistoryPoint } from '@/services/api';

export function useDashboardData() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [markets, setMarkets] = useState<MarketSymbol[]>([]);
  const [history, setHistory] = useState<EquityHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [statusData, tradesData, marketsData, historyData] = await Promise.all([
        apiService.getStatus(),
        apiService.getActiveTrades(),
        apiService.getMarketScanner(),
        apiService.getAccountHistory()
      ]);

      setStatus(statusData);
      setTrades(tradesData);
      setMarkets(marketsData);
      setHistory(historyData);
      setError(null);
    } catch (err) {
      console.error("Error fetching dashboard data:", err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return { status, trades, markets, history, loading, error, refetch: fetchData };
}
