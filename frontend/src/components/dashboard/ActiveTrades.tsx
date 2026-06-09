import { MoreHorizontal } from "lucide-react";

interface Trade {
  id: string | number;
  pair: string;
  type: string;
  lots: number;
  profit: string | number;
  status?: string;
}

interface ActiveTradesProps {
  data?: Trade[];
  onCloseTrade?: (id: string | number) => void;
  totalProfit?: number;
}

const defaultTrades: Trade[] = [
  { id: 1, pair: "EURUSD", type: "BUY", lots: 1.0, profit: "+$120.50", status: "Running" },
  { id: 2, pair: "XAUUSD", type: "SELL", lots: 0.5, profit: "-$45.20", status: "Running" },
  { id: 3, pair: "GBPUSD", type: "BUY", lots: 2.0, profit: "+$340.00", status: "Running" },
];

export function ActiveTrades({ data = [], onCloseTrade, totalProfit }: ActiveTradesProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold text-white">Active Trades</h3>
          {totalProfit !== undefined && (
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset ${
              totalProfit >= 0
                ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20"
                : "bg-rose-500/10 text-rose-400 ring-rose-500/20"
            }`}>
              {totalProfit >= 0 ? "+" : ""}{totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          )}
        </div>
        <button className="text-white/40 hover:text-white">
          <MoreHorizontal className="h-5 w-5" />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-white/40 border-b border-white/5">
              <th className="pb-3 font-medium">Pair</th>
              <th className="pb-3 font-medium">Type</th>
              <th className="pb-3 font-medium">Lots</th>
              <th className="pb-3 font-medium">Profit</th>
              <th className="pb-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {data.map((trade) => (
              <tr key={trade.id}>
                <td className="py-3 font-medium text-white">{trade.pair}</td>
                <td className={`py-3 ${trade.type === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {trade.type}
                </td>
                <td className="py-3 text-white/60">{trade.lots}</td>
                <td className={`py-3 font-mono ${String(trade.profit).startsWith('+') || Number(trade.profit) > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {typeof trade.profit === 'number' ? `${trade.profit.toFixed(2)}` : trade.profit}
                </td>
                <td className="py-3 text-right">
                  <button
                    onClick={() => onCloseTrade?.(trade.id)}
                    className="rounded bg-rose-500/10 px-2 py-1 text-xs text-rose-400 hover:bg-rose-500/20 transition-colors"
                  >
                    Close
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
