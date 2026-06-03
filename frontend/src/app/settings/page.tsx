"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useState, useEffect } from "react";
import { apiService } from "@/services/api";
import { useDashboardData } from "@/hooks/useDashboardData";
import { Settings as SettingsIcon, Globe, Terminal, Bell, Save } from "lucide-react";

export default function SettingsPage() {
  const { status } = useDashboardData();
  const [symbols, setSymbols] = useState<string>("");
  const [symbolsQuant, setSymbolsQuant] = useState<string>("");
  const [symbolsCorr, setSymbolsCorr] = useState<string>("");
  const [timeframe, setTimeframe] = useState<string>("H1");
  const [mt5Login, setMt5Login] = useState<string>("");
  const [mt5Password, setMt5Password] = useState<string>("");
  const [mt5Server, setMt5Server] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const config = await apiService.getConfig();
      setSymbols(config.symbols.join(", "));
      if (config.symbols_quant) setSymbolsQuant(config.symbols_quant.join(", "));
      if (config.symbols_corr) setSymbolsCorr(config.symbols_corr.join(", "));
      if (config.timeframe) setTimeframe(config.timeframe);
      if (config.mt5) {
        setMt5Login(config.mt5.login || "");
        setMt5Password(config.mt5.password || "");
        setMt5Server(config.mt5.server || "");
      }
    } catch (error) {
      console.error("Failed to load settings", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const symbolList = symbols.split(",").map(s => s.trim().toUpperCase()).filter(s => s !== "");
      const symbolListQuant = symbolsQuant.split(",").map(s => s.trim().toUpperCase()).filter(s => s !== "");
      const symbolListCorr = symbolsCorr.split(",").map(s => s.trim().toUpperCase()).filter(s => s !== "");
      await apiService.updateConfig({
        symbols: symbolList,
        symbols_quant: symbolListQuant,
        symbols_corr: symbolListCorr,
        timeframe: timeframe,
        mt5: {
          login: mt5Login,
          password: mt5Password,
          server: mt5Server
        }
      });
      setMessage("Settings updated successfully!");
      setTimeout(() => setMessage(""), 3000);
    } catch (error) {
      setMessage("Error updating settings.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-white">Loading...</div>;

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Header />
        <div className="p-8 max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-8">
            <SettingsIcon className="h-8 w-8 text-blue-500" />
            <h1 className="text-2xl font-bold">System Settings</h1>
          </div>

          <form onSubmit={handleSave} className="space-y-6">
            {/* Market Selection */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-2 mb-4 text-blue-400">
                <Globe className="h-5 w-5" />
                <h2 className="font-semibold">Market Coverage</h2>
              </div>

              <div className="grid grid-cols-1 gap-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm text-emerald-400/80 mb-1 font-medium">HMM Strategy Symbols (Strategy 1)</label>
                    <input
                      type="text"
                      value={symbols}
                      onChange={(e) => setSymbols(e.target.value)}
                      placeholder="EURUSD, GBPUSD, XAUUSD"
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-indigo-400/80 mb-1 font-medium">Quant Engine Symbols (Strategy 2)</label>
                    <input
                      type="text"
                      value={symbolsQuant}
                      onChange={(e) => setSymbolsQuant(e.target.value)}
                      placeholder="EURJPY, GBPJPY, EURUSD"
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-amber-400/80 mb-1 font-medium">Correlation Reversion Symbols (Strategy 3)</label>
                  <input
                    type="text"
                    value={symbolsCorr}
                    onChange={(e) => setSymbolsCorr(e.target.value)}
                    placeholder="EURUSD, GBPUSD, USDCHF, USDJPY, AUDUSD, NZDUSD, USDCAD"
                    className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                  />
                  <p className="text-xs text-white/40 mt-2">Correlation requires at least 2 highly correlated symbols to be monitored.</p>
                </div>

                <div>
                  <label className="block text-sm text-white/60 mb-1">AI Evaluation Timeframe</label>
                  <select
                    value={timeframe}
                    onChange={(e) => setTimeframe(e.target.value)}
                    className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="M1">M1 (1 Minute)</option>
                    <option value="M5">M5 (5 Minutes)</option>
                    <option value="M15">M15 (15 Minutes)</option>
                    <option value="M30">M30 (30 Minutes)</option>
                    <option value="H1">H1 (1 Hour)</option>
                    <option value="H4">H4 (4 Hours)</option>
                    <option value="D1">D1 (1 Day)</option>
                  </select>
                  <p className="text-xs text-white/40 mt-2">Applies to the currently active strategy.</p>
                </div>
              </div>
            </div>

            {/* Broker Connection */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 text-amber-400">
                  <Terminal className="h-5 w-5" />
                  <h2 className="font-semibold">MT5 Connectivity</h2>
                </div>
                <div className={`text-xs px-2 py-1 rounded-full ${status?.mt5_connected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                  {status?.mt5_connected ? 'Connected' : 'Disconnected'}
                </div>
              </div>

              {status?.mt5_error && (
                <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                  {status.mt5_error}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 pt-4 border-t border-white/5">
                <div>
                  <label className="block text-sm text-white/60 mb-1">Detected Account</label>
                  <div className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white/60 text-sm">
                    {status?.account_name || "Detecting..."} ({status?.account_number || "---"})
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-1">MT5 Server (Live)</label>
                  <div className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white/60 text-sm italic">
                    Connected to Terminal session
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-white/60 mb-1">MT5 Login ID</label>
                    <input
                      type="text"
                      value={mt5Login}
                      onChange={(e) => setMt5Login(e.target.value)}
                      placeholder="e.g. 50012345"
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-white/60 mb-1">MT5 Server Address</label>
                    <input
                      type="text"
                      value={mt5Server}
                      onChange={(e) => setMt5Server(e.target.value)}
                      placeholder="e.g. MetaQuotes-Demo"
                      className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-1">MT5 Password</label>
                  <input
                    type="password"
                    value={mt5Password}
                    onChange={(e) => setMt5Password(e.target.value)}
                    placeholder="Enter account password"
                    className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>
              <p className="text-xs text-white/40 mt-4 italic">Note: If credentials are left blank, the engine will attempt to use the last active session in your MT5 Terminal.</p>
            </div>

            {/* Notifications */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-2 mb-4 text-rose-400">
                <Bell className="h-5 w-5" />
                <h2 className="font-semibold">Alerts & Notifications</h2>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-white/60">Email on Drawdown Breach</span>
                  <div className="h-5 w-9 rounded-full bg-white/10"></div>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-sm text-white/60">Telegram Trade Signals</span>
                  <div className="h-5 w-9 rounded-full bg-white/10"></div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-emerald-400">{message}</p>
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-bold transition-colors"
              >
                <Save className="h-4 w-4" />
                {saving ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
