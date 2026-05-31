"use client";

import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface EquityData {
  time: string;
  equity: number;
}

interface EquityChartProps {
  data?: EquityData[];
}

const defaultData: EquityData[] = [
  { time: "00:00", equity: 10000 },
  { time: "04:00", equity: 10050 },
  { time: "08:00", equity: 9980 },
  { time: "12:00", equity: 10200 },
  { time: "16:00", equity: 10150 },
  { time: "20:00", equity: 10300 },
  { time: "23:59", equity: 10450 },
];

export function EquityChart({ data = defaultData }: EquityChartProps) {
  return (
    <div className="h-[300px] w-full rounded-xl border border-white/10 bg-white/5 p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Equity Curve</h3>
        <span className="text-xs text-white/40 font-mono uppercase tracking-wider">Live Updates</span>
      </div>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
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
              tickFormatter={(value) => `$${value}`}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#171717",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "8px",
                color: "#fff",
              }}
              itemStyle={{ color: "#10b981" }}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="#10b981"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorEquity)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
