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
  const [currentProcessing, setCurrentProcessing] = useState<string>("");
  const [params, setParams] = useState({
    strategy: "gold_scalper",
    symbol: "XAUUSD, GBPUSD",
    timeframe: "M30",
    date_from: "2023-01-01",
    date_to: "2023-12-31",
    lot_size: 0.1,
    profit_target: 0
  });

  const handleRunBacktest = async () => {
    const symbolList = params.symbol.split(",").map(s => s.trim()).filter(s => s !== "");
    if (symbolList.length === 0) {
      alert("Please enter at least one symbol.");
      return;
    }

    setLoading(true);
    setResult({
      total_trades: 0,
      total_usd: 0,
      win_rate: 0,
      trades: [],
      ohlcv: [],
      period: params.date_from + " to " + params.date_to,
      strategy: params.strategy
    });

    let allTrades: any[] = [];
    let combinedUSD = 0;

    // 1. CHUNKED REAL-TIME SIMULATION
    // Instead of one big request, we request 3-day blocks to show live progress
    const start = new Date(params.date_from);
    const end = new Date(params.date_to);

    try {
      for (const symbol of symbolList) {
        setCurrentProcessing(symbol);
        let currentBlockStart = new Date(start);

        while (currentBlockStart < end) {
          let currentBlockEnd = new Date(currentBlockStart);
          currentBlockEnd.setDate(currentBlockEnd.getDate() + 3); // 3-day chunks
          if (currentBlockEnd > end) currentBlockEnd = end;

          const data = await apiService.runBacktest({
            ...params,
            symbol: symbol,
            date_from: currentBlockStart.toISOString(),
            date_to: currentBlockEnd.toISOString()
          });

          if (!data.error && data.trades) {
            allTrades = [...allTrades, ...data.trades];
            combinedUSD += data.total_usd || 0;

            // Sort by time
            allTrades.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

            // UPDATE UI IMMEDIATELY (Simulating real-time discovery)
            setResult((prev: any) => ({
              ...prev,
              total_trades: allTrades.length,
              total_usd: combinedUSD,
              trades: [...allTrades].reverse(), // Show newest first in log
              win_rate: allTrades.length > 0 ? (allTrades.filter(t => t.usd > 0).length / allTrades.length * 100).toFixed(1) : "0.0"
            }));
          }

          currentBlockStart = currentBlockEnd;
        }
      }
    } catch (err) {
      console.error(err);
      alert("Backtest failed. Check connection to MetaTrader 5.");
    } finally {
      setLoading(false);
      setCurrentProcessing("");
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
            <div className="lg:col-span-3 space-y-4">
              {!result && !loading && (
                <div className="h-[300px] flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 text-white/20">
                  <Activity className="h-10 w-10 mb-4" />
                  <p className="text-sm font-medium uppercase tracking-widest opacity-40">Ready for Simulation</p>
                </div>
              )}

              {loading && (
                <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-lg py-2 px-4 flex items-center justify-between animate-pulse">
                  <div className="flex items-center gap-3">
                    <div className="h-1.5 w-1.5 bg-emerald-500 rounded-full animate-ping" />
                    <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">
                      Crunching Portfolio: {currentProcessing || 'Data Stream'}...
                    </span>
                  </div>
                  <span className="text-[10px] text-white/20 font-mono tracking-tighter">SECURE CLOUD BACKTEST</span>
                </div>
              )}

              {result && (
                <>
                  {/* Summary Cards Row 1 */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6 relative overflow-hidden">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Status</span>
                        {loading ? <Clock className="h-4 w-4 text-amber-500 animate-spin" /> : <AlertCircle className="h-4 w-4 text-emerald-500" />}
                      </div>
                      <p className="text-2xl font-bold">{loading ? "PROCESSING" : "COMPLETE"}</p>
                      {loading && (
                         <div className="absolute bottom-0 left-0 h-1 bg-amber-500/30 w-full">
                            <div className="h-full bg-amber-500 animate-[loading_2s_ease-in-out_infinite]" style={{width: '30%'}} />
                         </div>
                      )}
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Win Rate</span>
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                      </div>
                      <p className="text-2xl font-bold">{result.win_rate}%</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Total USD</span>
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                      </div>
                      <p className={`text-2xl font-bold ${result.total_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        ${result.total_usd.toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </p>
                      {currentProcessing && <p className="text-[10px] text-amber-500 animate-pulse mt-1">Calculating {currentProcessing}...</p>}
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-white/40 uppercase font-bold">Portfolio</span>
                        <Activity className="h-4 w-4 text-blue-500" />
                      </div>
                      <p className="text-2xl font-bold text-blue-400">{result.total_trades} trades</p>
                    </div>
                  </div>

                  {/* Summary Cards Row 2 - Trade Statistics */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-6">
                      <span className="text-[10px] text-emerald-400/60 uppercase font-bold block mb-1">Highest Profit</span>
                      <p className="text-xl font-bold text-emerald-400">
                        ${Math.max(...result.trades.map((t: any) => t.usd), 0).toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </p>
                    </div>
                    <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-6">
                      <span className="text-[10px] text-rose-400/60 uppercase font-bold block mb-1">Highest Loss</span>
                      <p className="text-xl font-bold text-rose-400">
                        ${Math.min(...result.trades.map((t: any) => t.usd), 0).toLocaleString(undefined, {minimumFractionDigits: 2})}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <span className="text-[10px] text-white/40 uppercase font-bold block mb-1">Average Profit</span>
                      <p className="text-xl font-bold text-emerald-400/80">
                        {(() => {
                          const wins = result.trades.filter((t: any) => t.usd > 0);
                          const avg = wins.length > 0 ? wins.reduce((s: any, t: any) => s + t.usd, 0) / wins.length : 0;
                          return `$${avg.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                        })()}
                      </p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                      <span className="text-[10px] text-white/40 uppercase font-bold block mb-1">Average Loss</span>
                      <p className="text-xl font-bold text-rose-400/80">
                        {(() => {
                          const losses = result.trades.filter((t: any) => t.usd < 0);
                          const avg = losses.length > 0 ? losses.reduce((s: any, t: any) => s + t.usd, 0) / losses.length : 0;
                          return `$${Math.abs(avg).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                        })()}
                      </p>
                    </div>
                  </div>

                    <div className="rounded-xl border border-white/10 bg-white/5 p-6 overflow-hidden">
                      <h3 className="font-bold text-white uppercase text-xs tracking-widest flex items-center gap-2 mb-4">
                        <div className={`h-2 w-2 rounded-full ${loading ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}`} />
                        {loading ? 'Real-time Simulation' : 'Full Execution Log'}
                      </h3>
                      <div className="max-h-[500px] overflow-y-auto pr-2">
                      <table className="w-full text-left border-collapse">
                        <thead className="text-xs text-white/40 uppercase bg-white/[0.02] sticky top-0 backdrop-blur-md">
                          <tr>
                            <th className="px-6 py-4 font-medium">Time</th>
                            <th className="px-6 py-4 font-medium">Asset/Type</th>
                            <th className="px-6 py-4 font-medium">Entry</th>
                            <th className="px-6 py-4 font-medium">Exit</th>
                            <th className="px-6 py-4 font-medium text-right">Result (USD)</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          {result.trades?.slice().reverse().map((t: any, idx: number) => (
                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                              <td className="px-6 py-4 text-xs font-mono text-white/60">{t.time}</td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.type.includes('BUY') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}`}>
                                  {t.type}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-sm font-medium">{t.entry.toFixed(t.symbol?.includes('JPY') ? 3 : 5)}</td>
                              <td className="px-6 py-4 text-sm font-medium">{t.exit.toFixed(t.symbol?.includes('JPY') ? 3 : 5)}</td>
                              <td className={`px-6 py-4 text-sm font-bold text-right ${t.usd >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {t.usd >= 0 ? '+' : ''}${t.usd.toFixed(2)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
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
