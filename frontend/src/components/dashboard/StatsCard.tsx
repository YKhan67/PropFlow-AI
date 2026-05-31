import { LucideIcon } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface StatsCardProps {
  title: string;
  value: string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  icon: LucideIcon;
  description?: string;
}

export function StatsCard({
  title,
  value,
  change,
  trend,
  icon: Icon,
  description,
}: StatsCardProps) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-white/60">{title}</p>
        <Icon className="h-4 w-4 text-white/40" />
      </div>
      <div className="mt-4 flex items-baseline gap-3">
        <h3 className="text-3xl font-bold tracking-tight text-white">{value}</h3>
        {change && (
          <span
            className={cn(
              "text-sm font-medium whitespace-nowrap",
              trend === "up" && "text-emerald-400",
              trend === "down" && "text-rose-400",
              trend === "neutral" && "text-white/40"
            )}
          >
            {change}
          </span>
        )}
      </div>
      {description && (
        <p className="mt-1 text-xs text-white/40">{description}</p>
      )}
    </div>
  );
}
