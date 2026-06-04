"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { apiService } from "@/services/api";
import { useState } from "react";
import { Activity, Calendar, Play, TrendingUp, AlertCircle, Clock } from "lucide-react";

export default function BacktestPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [playbackIdx, setPlaybackIdx] = useState(0);
  const [params, setParams] = useState({
    strategy: "hybrid_hmm",
    symbol: "XAUUSD",
    timeframe: "M30",
    date_from: "2023-01-01",
    date_to: "2023-12-31",
    lot_size: 0.1,
    profit_target: 100
  });

  const handleRunBacktest = async () => {
    setLoading(true);
    setResult(null);
    setPlaybackIdx(0);
    try {
      const data = await apiService.runBacktest({
        ...params,
        date_from: new Date(params.date_from).toISOString(),
        date_to: new Date(params.date_to).toISOString()
      });
      setResult(data);

      // Start playback simulation
      startPlayback(data.ohlcv.length);
    } catch (err) {
      console.error(err);
      alert("Backtest failed. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  const startPlayback = (totalBars: number) => {
    let current = 0;
    const interval = setInterval(() => {
      current += Math.ceil(totalBars / 100); // Fast forward playback
      if (current >= totalBars) {
        setPlaybackIdx(totalBars);
        clearInterval(interval);
      } else {
        setPlaybackIdx(current);
      }
    }, 50);
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Header />
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold">Historical Backtest</h1>
            <p className="text-white/60 text-sm">Validate your AI strategies against historical market data.</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Configuration Panel */}
            <div className="lg:col-span-1 space-y-6">
              <div className="rounded-xl border border-white/10 bg-white/5 p-6 space-y-4">
                <h3 className="font-bold text-white flex items-center gap-2">
                  <Activity className="h-4 w-4 text-emerald-500" />
                  Parameters
                </h3>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">Strategy</label>
                  <select
                    value={params.strategy}
                    onChange={(e) => setParams({...params, strategy: e.target.value})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="hybrid_hmm">Strategy 1: Hybrid AI</option>
                    <option value="quant_engine">Strategy 2: FX-QUANT</option>
                    <option value="correlation_reversion">Strategy 3: Correlation</option>
                    <option value="gold_scalper">Strategy 4: Gold Scalper</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">Symbol</label>
                  <input
                    type="text"
                    value={params.symbol}
                    onChange={(e) => setParams({...params, symbol: e.target.value.toUpperCase()})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                    placeholder="e.g. XAUUSD"
                  />
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">Timeframe</label>
                  <select
                    value={params.timeframe}
                    onChange={(e) => setParams({...params, timeframe: e.target.value})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  >
                    <option value="M5">5 Minutes</option>
                    <option value="M15">15 Minutes</option>
                    <option value="M30">30 Minutes</option>
                    <option value="H1">1 Hour</option>
                    <option value="H4">4 Hours</option>
                    <option value="D1">1 Day</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">Lot Size</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={params.lot_size}
                    onChange={(e) => setParams({...params, lot_size: parseFloat(e.target.value)})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">Profit Target (USD)</label>
                  <input
                    type="number"
                    step="10"
                    min="0"
                    value={params.profit_target}
                    onChange={(e) => setParams({...params, profit_target: parseFloat(e.target.value)})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                    placeholder="e.g. 100"
                  />
                  <p className="text-[10px] text-white/20 mt-1">Automatic exit when trade reaches this USD profit.</p>
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">From Date</label>
                  <input
                    type="date"
                    value={params.date_from}
                    onChange={(e) => setParams({...params, date_from: e.target.value})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs text-white/40 mb-1 uppercase tracking-wider">To Date</label>
                  <input
                    type="date"
                    value={params.date_to}
                    onChange={(e) => setParams({...params, date_to: e.target.value})}
                    className="w-full bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <button
                  onClick={handleRunBacktest}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 rounded-lg bg-emerald-500 py-3 text-sm font-bold text-white hover:bg-emerald-600 transition-colors disabled:opacity-50"
                >
                  {loading ? <Clock className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
                  {loading ? "Processing..." : "Run Backtest"}
                </button>
              </div>
            </div>

            {/* Results Panel */}
            <div className="lg:col-span-3 space-y-8">
              {!result && !loading && (
                <div className="h-full min-h-[400px] flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 text-white/20">
                  <Activity className="h-12 w-12 mb-4" />
                  <p>Configure parameters and click 'Run Backtest' to see historical performance.</p>
                </div>
              )}

              {loading && (
                <div className="h-full min-h-[400px] flex flex-col items-center justify-center rounded-xl border border-white/10 bg-white/5 animate-pulse">
                  <Activity className="h-12 w-12 mb-4 text-emerald-500/50" />
                  <p className="text-white/40 font-medium text-lg">AI is analyzing historical data...</p>
                  <p className="text-white/20 text-sm mt-2">This may take a minute for large date ranges.</p>
                </div>
              )}

              {result && !loading && (
                <>
                  {/* Summary Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Progress</span>
                        <Clock className="h-4 w-4 text-indigo-400" />
                      </div>
                      <p className="text-2xl font-bold">{Math.round((playbackIdx / (result.ohlcv?.length || 1)) * 100)}%</p>
                      <div className="w-full bg-white/5 h-1 rounded-full mt-2 overflow-hidden">
                        <div
                          className="bg-indigo-500 h-full transition-all duration-300"
                          style={{ width: `${(playbackIdx / (result.ohlcv?.length || 1)) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Win Rate</span>
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                      </div>
                      <p className="text-2xl font-bold">
                        {result.trades?.filter((t: any) => t.close_idx <= playbackIdx).length > 0
                          ? (result.trades.filter((t: any) => t.close_idx <= playbackIdx && t.pips > 0).length /
                             result.trades.filter((t: any) => t.close_idx <= playbackIdx).length * 100).toFixed(1)
                          : "0.0"}%
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Total USD</span>
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                      </div>
                      <p className={`text-2xl font-bold ${
                        result.trades?.filter((t: any) => t.close_idx <= playbackIdx).reduce((s: any, t: any) => s + t.usd, 0) >= 0
                          ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        ${result.trades?.filter((t: any) => t.close_idx <= playbackIdx).reduce((s: any, t: any) => s + t.usd, 0).toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Active Symbol</span>
                        <Activity className="h-4 w-4 text-blue-500" />
                      </div>
                      <p className="text-2xl font-bold text-blue-400">{result.symbol}</p>
                    </div>
                  </div>

                  {/* Trade Log */}
                  <div className="rounded-xl border border-white/10 bg-white/5 overflow-hidden">
                    <div className="p-6 border-b border-white/10 flex items-center justify-between">
                      <h3 className="font-bold text-white uppercase text-xs tracking-widest flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        Live Execution Log
                      </h3>
                      <span className="text-xs text-white/40">Showing {result.trades?.filter((t: any) => t.close_idx <= playbackIdx).length} executed orders</span>
                    </div>
                    <table className="w-full text-left">
                      <thead className="text-xs text-white/40 uppercase bg-white/[0.02]">
                        <tr>
                          <th className="px-6 py-4 font-medium">Time</th>
                          <th className="px-6 py-4 font-medium">Type</th>
                          <th className="px-6 py-4 font-medium">Entry</th>
                          <th className="px-6 py-4 font-medium">Exit</th>
                          <th className="px-6 py-4 font-medium">Result (USD)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {result.trades?.filter((t: any) => t.close_idx <= playbackIdx).slice(-15).reverse().map((t: any, idx: number) => (
                          <tr key={idx} className="hover:bg-white/5 transition-colors animate-in fade-in slide-in-from-left-2 duration-500">
                            <td className="px-6 py-4 text-sm font-mono">{t.time}</td>
                            <td className="px-6 py-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.type === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                                {t.type}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm font-medium">{t.entry}</td>
                            <td className="px-6 py-4 text-sm font-medium">{t.exit}</td>
                            <td className={`px-6 py-4 text-sm font-bold ${t.usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {t.usd >= 0 ? '+' : ''}${t.usd.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
