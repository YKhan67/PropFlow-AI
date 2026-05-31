import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface MarketData {
  symbol: string;
  price: string | number;
  change: string;
  trend: "up" | "down";
}

interface MarketScannerProps {
  data?: MarketData[];
}

const defaultMarkets: MarketData[] = [
  { symbol: "EURUSD", price: "1.08452", change: "+0.12%", trend: "up" },
  { symbol: "GBPUSD", price: "1.26781", change: "-0.05%", trend: "down" },
  { symbol: "USDJPY", price: "150.234", change: "+0.45%", trend: "up" },
  { symbol: "AUDUSD", price: "0.65432", change: "-0.21%", trend: "down" },
  { symbol: "XAUUSD", price: "2034.12", change: "+0.89%", trend: "up" },
];

export function MarketScanner({ data = defaultMarkets }: MarketScannerProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6">
      <h3 className="mb-4 text-lg font-semibold text-white">Market Scanner</h3>
      <div className="space-y-4">
        {data.map((m) => (
          <div
            key={m.symbol}
            className="flex items-center justify-between border-b border-white/5 pb-2 last:border-0"
          >
            <div>
              <p className="font-bold text-white">{m.symbol}</p>
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
