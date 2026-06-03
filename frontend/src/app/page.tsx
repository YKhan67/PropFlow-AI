"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { StatsCard } from "@/components/dashboard/StatsCard";
import { EquityChart } from "@/components/charts/EquityChart";
import { MarketScanner } from "@/components/dashboard/MarketScanner";
import { ActiveTrades } from "@/components/dashboard/ActiveTrades";
import { Wallet, TrendingUp, AlertCircle, Activity, Play, Square, XCircle } from "lucide-react";
import { useDashboardData } from "@/hooks/useDashboardData";
import { apiService } from "@/services/api";
import { useState } from "react";

export default function Dashboard() {
  const { status, trades, markets, history, loading, error, refetch } = useDashboardData();
  const [actionLoading, setActionLoading] = useState(false);

  const handleToggleEngine = async () => {
    if (!status) return;
    setActionLoading(true);
    try {
      if (status.engine_running) {
        await apiService.stopEngine();
      } else {
        await apiService.startEngine();
      }
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to toggle engine");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseAll = async () => {
    if (!confirm("Are you sure you want to close ALL active trades?")) return;
    setActionLoading(true);
    try {
      await apiService.closeAllTrades();
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to close trades");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseTrade = async (id: string | number) => {
    setActionLoading(true);
    try {
      await apiService.closeTrade(id);
      await refetch();
    } catch (err) {
      console.error(err);
      alert("Failed to close trade");
    } finally {
      setActionLoading(false);
    }
  };

  const accountMetrics = status?.account_metrics;

  // Format history for EquityChart
  const chartData = history.length > 0 
    ? history.map(p => ({
        time: new Date(p.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        equity: p.equity
      }))
    : undefined;

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      
      <main className="flex-1 overflow-y-auto">
        <Header />
        
        <div className="p-8">
          <div className="mb-8 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Trading Overview</h1>
              <p className="text-white/60 text-sm">
                {loading ? "Loading system status..." : error ? `Error: ${error}` : status?.engine_running ? `System Active [${
                  status.active_strategy === 'hybrid_hmm' ? 'Hybrid AI' :
                  status.active_strategy === 'quant_engine' ? 'FX-QUANT' :
                  'Correlation'
                }]` : "System is idle."}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {trades.length > 0 && (
                <button
                  onClick={handleCloseAll}
                  disabled={actionLoading || loading}
                  className="flex items-center gap-2 rounded-lg bg-rose-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 disabled:opacity-50"
                >
                  <XCircle className="h-4 w-4" /> Close All Trades
                </button>
              )}
              <button
                onClick={handleToggleEngine}
                disabled={actionLoading || loading}
                className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  status?.engine_running 
                    ? "bg-rose-500/10 text-rose-400 hover:bg-rose-500/20" 
                    : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                } disabled:opacity-50`}
              >
                {status?.engine_running ? (
                  <><Square className="h-4 w-4" /> Stop Engine</>
                ) : (
                  <><Play className="h-4 w-4" /> Start Engine</>
                )}
              </button>
              <div className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${
                status?.engine_running ? "bg-emerald-500/10 text-emerald-400" : "bg-white/5 text-white/40"
              }`}>
                <Activity className="h-4 w-4" />
                <span className="text-sm font-medium">{status?.engine_running ? "System Online" : "System Offline"}</span>
              </div>
            </div>
          </div>

          <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-5">
            <StatsCard
              title="Account Equity"
              value={status?.risk_status?.current_equity !== undefined ? `$${status.risk_status.current_equity.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "$0.00"}
              change={status?.risk_status ? `${((status.risk_status.current_equity - status.risk_status.starting_balance) / status.risk_status.starting_balance * 100).toFixed(2)}%` : undefined}
              trend={status?.risk_status && status.risk_status.current_equity >= status.risk_status.starting_balance ? "up" : "down"}
              icon={Activity}
              description="Floating account value"
            />
            <StatsCard
              title="Account Balance"
              value={status?.balance !== undefined ? `$${status.balance.toLocaleString(undefined, {minimumFractionDigits: 2})}` : "$0.00"}
              icon={Wallet}
              description="Settled account balance"
              trend="neutral"
            />
            <StatsCard
              title="Daily Drawdown"
              value={status?.risk_status?.daily_drawdown !== undefined ? `${status.risk_status.daily_drawdown.toFixed(2)}%` : "0.00%"}
              change={status?.risk_status ? `Limit: ${status.risk_status.max_daily_drawdown.toFixed(1)}%` : undefined}
              trend={status?.risk_status && status.risk_status.daily_drawdown < status.risk_status.max_daily_drawdown ? "up" : "down"}
              icon={TrendingUp}
              description="Current session drawdown"
            />
            <StatsCard
              title="Total Drawdown"
              value={status?.risk_status?.total_drawdown !== undefined ? `${status.risk_status.total_drawdown.toFixed(2)}%` : "0.00%"}
              change={status?.risk_status ? `Limit: ${status.risk_status.max_total_drawdown.toFixed(1)}%` : undefined}
              trend="neutral"
              icon={AlertCircle}
              description="Against starting balance"
            />
            <StatsCard
              title="Active Trades"
              value={status?.active_trades_count?.toString() || "0"}
              trend="up"
              icon={Activity}
              description="Current positions"
            />
          </div>

          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-8">
              <EquityChart data={chartData} />
              <ActiveTrades 
                data={trades.map(t => ({
                  id: t.id,
                  pair: t.symbol,
                  type: t.type,
                  lots: t.volume,
                  profit: t.profit
                }))}
                onCloseTrade={handleCloseTrade}
                totalProfit={trades.reduce((sum, t) => sum + (typeof t.profit === 'number' ? t.profit : 0), 0)}
              />
            </div>
            <div className="space-y-8">
              <MarketScanner 
                data={markets.map(m => ({
                  symbol: m.symbol,
                  price: m.bid, // Using bid as display price
                  change: `${m.change >= 0 ? '+' : ''}${m.change.toFixed(2)}%`,
                  trend: m.trend,
                  regime: m.regime,
                  pnl: m.pnl
                }))}
              />
              <div className="rounded-xl border border-white/10 bg-gradient-to-br from-emerald-500/20 to-blue-500/20 p-6">
                <h3 className="font-bold text-white mb-2">Upgrade to Pro</h3>
                <p className="text-sm text-white/60 mb-4">Get access to advanced AI strategies and multi-account management.</p>
                <button className="w-full rounded-lg bg-emerald-500 py-2 text-sm font-bold text-white hover:bg-emerald-600 transition-colors">
                  Upgrade Now
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
