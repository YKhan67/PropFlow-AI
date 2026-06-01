"use client";

import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { useDashboardData } from "@/hooks/useDashboardData";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { BarChart3, TrendingUp, Target, Award, Wallet } from "lucide-react";
import { useState, useEffect, useMemo } from "react";
import { apiService, HistoricalTrade } from "@/services/api";

export default function AnalyticsPage() {
  const { status, loading: dashboardLoading } = useDashboardData();
  const [history, setHistory] = useState<HistoricalTrade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await apiService.getTradeHistory(30);
        setHistory(data);
      } catch (error) {
        console.error("Failed to fetch trade history", error);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  const stats = useMemo(() => {
    if (history.length === 0) return { winRate: 0, profitFactor: 0, totalNet: 0, grossPnL: 0, winCount: 0, lossCount: 0, winUSD: 0, lossUSD: 0 };

    // Grouping: In MT5, a trade is usually 1 Entry Deal and 1 Exit Deal.
    // Profits are recorded on Exit deals (entry 1 or 2).
    // Commissions are often recorded on the Entry deal (entry 0).

    // 1. Identify closing deals (where profit was realized)
    const closingDeals = history.filter(t => t.profit !== 0);

    // 2. Calculate PnL components
    // Gross PnL is the sum of raw profits
    const grossPnL = closingDeals.reduce((sum, t) => sum + t.profit, 0);

    // Total fees from ALL deals in history
    const totalComm = history.reduce((sum, t) => sum + t.commission, 0);
    const totalSwap = history.reduce((sum, t) => sum + t.swap, 0);
    const netProfit = grossPnL + totalComm + totalSwap;

    // 3. Win/Loss metrics
    // A win is a closing deal where profit > 0
    const wins = closingDeals.filter(t => t.profit > 0);
    const losses = closingDeals.filter(t => t.profit < 0);

    const winRate = closingDeals.length > 0 ? (wins.length / closingDeals.length) * 100 : 0;

    const winUSD = wins.reduce((sum, t) => sum + t.profit, 0);
    const lossUSD = Math.abs(losses.reduce((sum, t) => sum + t.profit, 0));

    // Profit Factor: Sum of profits from winning deals / Sum of losses from losing deals
    const profitFactor = lossUSD === 0 ? (winUSD > 0 ? 99 : 0) : winUSD / lossUSD;

    return {
      winRate: winRate.toFixed(1),
      profitFactor: profitFactor.toFixed(2),
      grossPnL: grossPnL.toFixed(2),
      totalNet: netProfit.toFixed(2),
      winCount: wins.length,
      lossCount: losses.length,
      winUSD: winUSD.toFixed(2),
      lossUSD: lossUSD.toFixed(2)
    };
  }, [history]);

  const chartData = useMemo(() => {
    const symbolMap: Record<string, number> = {};
    // Aggregate EVERY deal's result (profit+comm+swap) per symbol for accurate per-pair net profit
    history.forEach(t => {
      if (!t.symbol) return;
      const net = t.profit + t.commission + t.swap;
      symbolMap[t.symbol] = (symbolMap[t.symbol] || 0) + net;
    });

    return Object.entries(symbolMap)
      .map(([name, profit]) => ({
        name,
        profit: parseFloat(profit.toFixed(2))
      }))
      .filter(item => item.name !== "" && item.name !== "0") // Filter out empty symbols
      .sort((a, b) => b.profit - a.profit);
  }, [history]);

  const distributionData = [
    { name: 'Wins', value: parseFloat(stats.winUSD), fill: '#10b981' },
    { name: 'Losses', value: parseFloat(stats.lossUSD), fill: '#f43f5e' },
  ];

  if (loading || dashboardLoading) return <div className="p-8 text-white">Loading Real-Time Analytics...</div>;

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Header />
        <div className="p-8">
          <div className="flex items-center gap-3 mb-8">
            <BarChart3 className="h-8 w-8 text-indigo-500" />
            <h1 className="text-2xl font-bold">Performance Analytics (Live)</h1>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-2 mb-2 text-indigo-400">
                <Target className="h-5 w-5" />
                <span className="text-sm font-medium">Win Rate</span>
              </div>
              <div className="text-3xl font-bold">{stats.winRate}%</div>
              <p className="text-xs text-white/40 mt-1">{stats.winCount} Wins / {stats.lossCount} Losses</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-2 mb-2 text-emerald-400">
                <Award className="h-5 w-5" />
                <span className="text-sm font-medium">Profit Factor</span>
              </div>
              <div className="text-3xl font-bold">{stats.profitFactor}</div>
              <p className="text-xs text-white/40 mt-1">Efficiency Ratio</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <div className="flex items-center gap-2 mb-2 text-blue-400">
                <Wallet className="h-5 w-5" />
                <span className="text-sm font-medium">Account Balance</span>
              </div>
              <div className="text-3xl font-bold">${status?.balance?.toLocaleString(undefined, {minimumFractionDigits: 2}) || "0.00"}</div>
              <p className="text-xs text-white/40 mt-1">Current settled funds</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-6 bg-gradient-to-br from-emerald-500/10 to-transparent">
              <div className="flex items-center gap-2 mb-2 text-emerald-400">
                <TrendingUp className="h-5 w-5" />
                <span className="text-sm font-medium">Net Profit</span>
              </div>
              <div className="text-3xl font-bold">${stats.totalNet}</div>
              <p className="text-xs text-white/40 mt-1">Total realized PnL</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Profit by Symbol */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <h3 className="font-semibold mb-6">Realized Profit by Symbol ($)</h3>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                    <XAxis dataKey="name" stroke="#ffffff40" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#ffffff40" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#111', border: '1px solid #ffffff20', borderRadius: '8px' }}
                      itemStyle={{ color: '#fff' }}
                    />
                    <Bar dataKey="profit">
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.profit >= 0 ? '#6366f1' : '#f43f5e'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Win/Loss Distribution */}
            <div className="rounded-xl border border-white/10 bg-white/5 p-6">
              <h3 className="font-semibold mb-6">Trade Outcome Distribution ($)</h3>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={distributionData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" horizontal={false} />
                    <XAxis type="number" stroke="#ffffff40" fontSize={12} hide />
                    <YAxis dataKey="name" type="category" stroke="#ffffff40" fontSize={12} tickLine={false} axisLine={false} width={60} />
                    <Tooltip
                      cursor={{fill: '#ffffff05'}}
                      contentStyle={{ backgroundColor: '#111', border: '1px solid #ffffff20', borderRadius: '8px' }}
                      itemStyle={{ color: '#fff' }}
                    />
                    <Bar
                      dataKey="value"
                      radius={[0, 4, 4, 0]}
                      label={{
                        position: 'right',
                        fill: '#fff',
                        fontSize: 10,
                        formatter: (val: any) => `$${val.toFixed(2)}`
                      }}
                    >
                      {distributionData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
