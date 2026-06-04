"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, LineChart, ShieldAlert, Settings, HelpCircle, LogOut, Activity } from "lucide-react";

export function Sidebar() {
  const pathname = usePathname();

  const items = [
    { icon: LayoutDashboard, label: "Dashboard", href: "/" },
    { icon: LineChart, label: "Analytics", href: "/analytics" },
    { icon: Activity, label: "Backtest", href: "/backtest" },
    { icon: ShieldAlert, label: "Risk Manager", href: "/risk" },
    { icon: Settings, label: "Settings", href: "/settings" },
  ];

  return (
    <div className="flex h-screen w-64 flex-col border-r border-white/10 bg-[#0a0a0a] p-6 sticky top-0">
      <div className="mb-10 flex items-center gap-3 px-2">
        <Link href="/" className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-emerald-500" />
          <span className="text-xl font-bold tracking-tight text-white">PropFlow AI</span>
        </Link>
      </div>

      <nav className="flex-1 space-y-4">
        {items.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`flex w-full items-center gap-4 rounded-lg px-4 py-3 text-base font-medium transition-colors ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-white/60 hover:bg-white/5 hover:text-white"
              }`}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto space-y-2 pt-6">
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-white/60 hover:bg-white/5 hover:text-white">
          <HelpCircle className="h-5 w-5" />
          Support
        </button>
        <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-rose-400 hover:bg-rose-500/10">
          <LogOut className="h-5 w-5" />
          Logout
        </button>
      </div>
    </div>
  );
}
