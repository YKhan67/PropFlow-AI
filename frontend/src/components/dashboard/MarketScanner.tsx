import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface MarketData {
  symbol: string;
  price: string | number;
  change: string;
  trend: "up" | "down";
  regime?: string;
  pnl?: number;
}

interface MarketScannerProps {
  data?: MarketData[];
  onSelectSymbol?: (symbol: string) => void;
  selectedSymbol?: string;
  totalPnL?: number;
}

const defaultMarkets: MarketData[] = [
  { symbol: "EURUSD", price: "1.08452", change: "+0.12%", trend: "up", regime: "ranging" },
  { symbol: "GBPUSD", price: "1.26781", change: "-0.05%", trend: "down", regime: "trending" },
];

export function MarketScanner({ data = defaultMarkets, onSelectSymbol, selectedSymbol, totalPnL }: MarketScannerProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="mb-4 flex items-center gap-3">
        <h3 className="text-lg font-semibold text-white">Market Scanner</h3>
        {totalPnL !== undefined && totalPnL !== 0 && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset ${
            totalPnL >= 0
              ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/20"
              : "bg-rose-500/10 text-rose-400 ring-rose-500/20"
          }`}>
            {totalPnL >= 0 ? "+" : ""}{totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        )}
      </div>
      <div className="space-y-4">
        {data.map((m) => (
          <div
            key={m.symbol}
            onClick={() => {
              console.log("Selected symbol:", m.symbol);
              onSelectSymbol?.(m.symbol);
            }}
            className={`flex items-center justify-between border-b border-white/5 pb-2 last:border-0 cursor-pointer hover:bg-white/10 transition-all p-2 rounded-lg ${
              selectedSymbol === m.symbol ? 'ring-2 ring-blue-500 bg-blue-500/10' : ''
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="font-bold text-white">{m.symbol}</p>
                {m.regime && (
                  <span className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-white/40 border border-white/10">
                    {m.regime}
                  </span>
                )}
                {m.pnl !== undefined && m.pnl !== 0 && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                    m.pnl >= 0
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  }`}>
                    {m.pnl >= 0 ? "+" : ""}{m.pnl}
                  </span>
                )}
              </div>
              <p className="text-sm text-white/40">{m.price}</p>
            </div>
            <div
              className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium ${
                m.trend === "up"
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "bg-rose-500/10 text-rose-400"
              }`}
            >
              {m.trend === "up" ? (
                <ArrowUpRight className="h-3 w-3" />
              ) : (
                <ArrowDownRight className="h-3 w-3" />
              )}
              {m.change}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
