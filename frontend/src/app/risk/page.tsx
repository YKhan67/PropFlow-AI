"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useState, useEffect } from "react";
import { apiService, RiskConfig } from "@/services/api";
import { Shield, AlertTriangle, Scale, Wallet, Save } from "lucide-react";

export default function RiskPage() {
  const [config, setConfig] = useState<RiskConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const fullConfig = await apiService.getConfig();
      setConfig(fullConfig.risk);
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
                    <label className="block text-sm text-white/60 mb-1">Min Time Between Trades (Mins)</label>
                    <input
                      type="number"
                      step="1"
                      value={config?.min_time_between_trades || 0}
                      onChange={(e) => updateField("min_time_between_trades", parseInt(e.target.value))}
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                    <p className="text-xs text-white/40 mt-2">Safety cooldown period per symbol to prevent rapid over-trading.</p>
                  </div>
                </div>
              </div>
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
