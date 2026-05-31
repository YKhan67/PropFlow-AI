import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function AnalyticsPage() {
  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Header />
        <div className="p-8">
          <h1 className="text-2xl font-bold mb-4">Analytics</h1>
          <div className="rounded-xl border border-white/10 bg-white/5 p-12 text-center">
            <p className="text-white/60">Advanced analytics and performance insights coming soon.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
