import { Search, Bell, User } from "lucide-react";

export function Header() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-white/10 bg-[#0a0a0a]/50 px-8 backdrop-blur-md">
      <div className="relative w-96">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
        <input
          type="text"
          placeholder="Search pairs or strategies..."
          className="w-full rounded-lg bg-white/5 py-2 pl-10 pr-4 text-sm text-white placeholder-white/20 outline-none ring-1 ring-white/10 focus:ring-emerald-500/50"
        />
      </div>

      <div className="flex items-center gap-6">
        <button className="relative text-white/60 hover:text-white">
          <Bell className="h-5 w-5" />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-500" />
        </button>
        <div className="flex items-center gap-3 rounded-full bg-white/5 py-1.5 pl-1.5 pr-4 ring-1 ring-white/10">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-500">
            <User className="h-4 w-4" />
          </div>
          <span className="text-sm font-medium text-white">John Doe</span>
        </div>
      </div>
    </header>
  );
}
