"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface PriceData {
  time: string;
  price: number;
}

interface PriceChartProps {
  data: PriceData[];
  title: string;
  color?: string;
}

export function PriceChart({ data, title, color = "#6366f1" }: PriceChartProps) {
  return (
    <div className="h-[300px] w-full rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <span className="text-xs text-white/40 font-mono uppercase tracking-wider">Market Data</span>
      </div>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`colorPrice-${title}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="time"
              stroke="#ffffff40"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#ffffff40"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              domain={['auto', 'auto']}
              tickFormatter={(val) => val.toFixed(2)}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#171717",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                color: "#fff",
              }}
              itemStyle={{ color: color }}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={color}
              strokeWidth={2}
              fillOpacity={1}
              fill={`url(#colorPrice-${title})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
