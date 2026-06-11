"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useState, useEffect } from "react";
import { apiService, RiskConfig } from "@/services/api";
import { Shield, AlertTriangle, Scale, Wallet, Save } from "lucide-react";

export default function RiskPage() {
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [cooldownStr, setCooldownStr] = useState("00:00");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [autoZeroStatus, setAutoZeroStatus] = useState("Waiting");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const [fullConfig, status] = await Promise.all([
        apiService.getConfig(),
        apiService.getStatus()
      ]);
      setConfig(fullConfig.risk);
      setAutoZeroStatus(status.auto_zero_status || "Waiting");
      setCooldownStr(formatSecondsToMMSS(fullConfig.risk.min_time_between_trades || 0));
    } catch (error) {
      console.error("Failed to load risk config", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;
    setSaving(true);
    setMessage("");
    try {
      await apiService.updateConfig({ risk: config });
      setCooldownStr(formatSecondsToMMSS(config.min_time_between_trades || 0));
      setMessage("Risk parameters updated successfully!");
      setTimeout(() => setMessage(""), 3000);
    } catch (error) {
      setMessage("Error updating risk parameters.");
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof RiskConfig, value: string | number | boolean) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
  };

  const formatSecondsToMMSS = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const parseMMSSToSeconds = (mmss: string) => {
    if (!mmss.includes(':')) return parseInt(mmss) || 0;
    const parts = mmss.split(':');
    const mins = parseInt(parts[0]) || 0;
    const secs = parseInt(parts[1]) || 0;
    return (mins * 60) + secs;
  };

  if (loading) return <div className="p-8 text-white">Loading...</div>;

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Header />
        <div className="p-8 max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-8">
            <Shield className="h-8 w-8 text-emerald-500" />
            <h1 className="text-2xl font-bold">Risk Management Module</h1>
          </div>

          <form onSubmit={handleSave} className="space-y-6">
            {/* Strategy Selection */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6 border-emerald-500/30 bg-emerald-500/5">
              <div className="flex items-center gap-2 mb-4 text-emerald-400">
                <Shield className="h-5 w-5" />
                <h2 className="font-semibold">Active Trading Strategy</h2>
              </div>
              <div>
                <select
                  value={config?.active_strategy || "hybrid_hmm"}
                  onChange={(e) => updateField("active_strategy", e.target.value as any)}
                  className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="hybrid_hmm">Strategy 1: Hybrid AI (Momentum + HMM)</option>
                  <option value="quant_engine">Strategy 2: FX-QUANT-ENGINE (Stat-Arb & Synthetic)</option>
                  <option value="correlation_reversion">Strategy 3: Correlation Reversion (Pair Basket)</option>
                  <option value="gold_scalper">Strategy 4: Gold Scalper (RSI + ADX)</option>
                </select>
                <p className="text-xs text-white/40 mt-2">
                  {config?.active_strategy === "hybrid_hmm"
                    ? "Uses HMM for regime detection and technical indicators for momentum entry."
                    : config?.active_strategy === "quant_engine"
                    ? "Institutional-grade system using statistical arbitrage, cointegration, and synthetic pair pricing."
                    : config?.active_strategy === "correlation_reversion"
                    ? "Strictly correlation-based divergence trading. Opens synchronized two-pair baskets."
                    : "Aggressive Gold scalper using RSI, ADX and candle structure for XAUUSD breakouts."}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Drawdown Settings */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                <div className="flex items-center gap-2 mb-4 text-emerald-400">
                  <AlertTriangle className="h-5 w-5" />
                  <h2 className="font-semibold">Drawdown Limits</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Max Daily Drawdown (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={config ? config.max_daily_drawdown * 100 : 0}
                      onChange={(e) => updateField("max_daily_drawdown", parseFloat(e.target.value) / 100)}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Max Total Drawdown (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={config ? config.max_total_drawdown * 100 : 0}
                      onChange={(e) => updateField("max_total_drawdown", parseFloat(e.target.value) / 100)}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              </div>

              {/* Account Settings */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                <div className="flex items-center gap-2 mb-4 text-blue-400">
                  <Wallet className="h-5 w-5" />
                  <h2 className="font-semibold">Account Parameters</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Starting Balance ($)</label>
                    <input
                      type="number"
                      value={config?.account_balance || 0}
                      onChange={(e) => updateField("account_balance", parseFloat(e.target.value))}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm text-white/60">Auto Scale Down Excess</span>
                    <button
                      type="button"
                      onClick={() => updateField("scale_down_excess", !config?.scale_down_excess)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config?.scale_down_excess ? 'bg-emerald-500' : 'bg-white/10'}`}
                    >
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config?.scale_down_excess ? 'translate-x-6' : 'translate-x-1'}`} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Position Sizing */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-6 md:col-span-2">
                <div className="flex items-center gap-2 mb-4 text-amber-400">
                  <Scale className="h-5 w-5" />
                  <h2 className="font-semibold">Position Sizing Rules</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Max Position Size (Lots)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={config?.max_position_size || 0}
                      onChange={(e) => updateField("max_position_size", parseFloat(e.target.value))}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                    <p className="text-xs text-white/40 mt-2">Hard limit for any single trade execution.</p>
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Max Active Trades</label>
                    <input
                      type="number"
                      step="1"
                      value={config?.max_active_trades || 0}
                      onChange={(e) => updateField("max_active_trades", parseInt(e.target.value))}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                    <p className="text-xs text-white/40 mt-2">Maximum number of concurrent open positions.</p>
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Global Profit Target ($)</label>
                    <input
                      type="number"
                      step="1"
                      value={config?.global_take_profit || 0}
                      onChange={(e) => updateField("global_take_profit", parseFloat(e.target.value))}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                    <p className="text-xs text-white/40 mt-2">Automatically close all trades when total unrealized profit reaches this amount. Set to 0 to disable.</p>
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">Min Time Between Trades (MM:SS)</label>
                    <input
                      type="text"
                      placeholder="05:00"
                      value={cooldownStr}
                      onChange={(e) => {
                        const val = e.target.value.replace(/[^0-9:]/g, ''); // Only numbers and colons
                        setCooldownStr(val);
                        // Update config immediately if valid format MM:SS
                        if (/^\d{1,2}:\d{2}$/.test(val)) {
                          const seconds = parseMMSSToSeconds(val);
                          updateField("min_time_between_trades", seconds);
                        }
                      }}
                      onBlur={() => {
                        // Cleanup formatting on blur (e.g. 5:0 -> 05:00)
                        if (config) {
                          setCooldownStr(formatSecondsToMMSS(config.min_time_between_trades || 0));
                        }
                      }}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                    <p className="text-[10px] text-white/40 mt-2">
                      Current delay: <span className="text-amber-400">{config?.min_time_between_trades || 0} seconds</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Auto Zero Buy/Sell */}
              <div className="rounded-xl border border-white/10 bg-white/5 p-6 md:col-span-2">
                <div className="flex items-center gap-2 mb-4 text-emerald-400">
                  <Shield className="h-5 w-5" />
                  <h2 className="font-semibold">Auto Zero Buy/Sell</h2>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-white/60">Enable Auto Zero Buy/Sell</span>
                      <button
                        type="button"
                        onClick={() => updateField("auto_zero_enabled", !config?.auto_zero_enabled)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${config?.auto_zero_enabled ? 'bg-emerald-500' : 'bg-white/10'}`}
                      >
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${config?.auto_zero_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                      </button>
                    </div>
                    <div>
                      <label className="block text-sm text-white/60 mb-1">Auto Zero Loss Limit ($)</label>
                      <input
                        type="number"
                        step="1"
                        max="-1"
                        value={config?.auto_zero_loss_limit || -500}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateField("auto_zero_loss_limit", val);
                        }}
                        className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500"
                      />
                      {config && (config.auto_zero_loss_limit || 0) >= 0 && (
                        <p className="text-xs text-rose-400 mt-1">Loss limit must be a negative number.</p>
                      )}
                    </div>
                  </div>
                  <div className="rounded-lg bg-black/40 p-4 border border-white/5">
                    <h3 className="text-xs font-bold text-white/40 uppercase mb-3">Current Status</h3>
                    <div className="flex items-center gap-3">
                      <div className={`h-3 w-3 rounded-full animate-pulse ${
                        autoZeroStatus === 'Executed' ? 'bg-emerald-500' :
                        autoZeroStatus === 'Triggered' ? 'bg-amber-500' :
                        autoZeroStatus === 'Failed' ? 'bg-rose-500' : 'bg-blue-500'
                      }`} />
                      <span className="text-xl font-mono font-bold tracking-tight">{autoZeroStatus}</span>
                    </div>
                    <p className="text-[10px] text-white/30 mt-4 leading-relaxed">
                      Automatically neutralizes opposing exposure when Net P/L hits the threshold.
                      Trigger resets once Net P/L recovers above the limit.
                    </p>
                  </div>
                </div>
              </div>

              {/* Quant Engine Specific Settings */}
              {config?.active_strategy === "quant_engine" && (
                <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-6 md:col-span-2">
                  <div className="flex items-center gap-2 mb-4 text-indigo-400">
                    <Scale className="h-5 w-5" />
                    <h2 className="font-semibold">FX-QUANT-ENGINE Parameters</h2>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm text-white/60 mb-1">Arbitrage Z-Score Entry</label>
                      <input
                        type="number"
                        step="0.1"
                        value={config?.quant_zscore_entry || 2.0}
                        onChange={(e) => updateField("quant_zscore_entry", parseFloat(e.target.value))}
                        className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                      />
                      <p className="text-xs text-white/40 mt-2">Standard deviations from mean to trigger trade (Default: 2.0).</p>
                    </div>
                    <div>
                      <label className="block text-sm text-white/60 mb-1">Arbitrage Z-Score Exit</label>
                      <input
                        type="number"
                        step="0.1"
                        value={config?.quant_zscore_exit || 0.5}
                        onChange={(e) => updateField("quant_zscore_exit", parseFloat(e.target.value))}
                        className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                      />
                      <p className="text-xs text-white/40 mt-2">Target Z-Score for mean reversion exit (Default: 0.5).</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-4">
              <p className={`text-sm ${message.includes("Error") ? "text-rose-400" : "text-emerald-400"}`}>
                {message}
              </p>
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-bold transition-colors"
              >
                <Save className="h-4 w-4" />
                {saving ? "Saving..." : "Save Risk Parameters"}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
