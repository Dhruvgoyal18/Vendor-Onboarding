"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getDashboardStats, getDashboardHistory } from "@/lib/api";
import { DashboardStats, PaginatedVendors, Vendor } from "@/lib/types";
import StatusBadge from "@/components/StatusBadge";
import {
  BarChart3,
  Search,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  LogOut,
  RefreshCw,
  Plus,
  TrendingUp,
  CheckCircle,
  Clock,
  XCircle,
  AlertCircle,
  Loader2,
  Building2,
  Filter,
  ArrowUpRight,
  Calendar,
  LayoutDashboard,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

// ─── Stat Card ────────────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
  glow,
  isActive,
  onClick,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bg: string;
  glow: string;
  isActive?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`card text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-600/80 group w-full
        ${isActive ? `border-opacity-100 ${glow}` : ""}`}
    >
      <div className="flex items-start justify-between gap-2 mb-4">
        <div
          className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center shadow-md ${glow} group-hover:scale-110 transition-transform`}
        >
          <Icon className={`w-[18px] h-[18px] ${color}`} />
        </div>
        {isActive && (
          <span className="text-xs text-violet-400 bg-violet-500/10 px-1.5 py-0.5 rounded-full border border-violet-500/20">
            Filtered
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-white tabular-nums">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </button>
  );
}

// ─── Runs Table Row ───────────────────────────────────────────────────────────────
function RunRow({
  vendor,
  onClick,
}: {
  vendor: Vendor;
  onClick: () => void;
}) {
  const timeAgo = formatDistanceToNow(new Date(vendor.created_at), {
    addSuffix: true,
  });

  return (
    <tr
      onClick={onClick}
      className="border-b border-slate-800/60 hover:bg-slate-800/30 cursor-pointer transition-colors group"
    >
      <td className="py-3.5 pl-4 pr-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center flex-shrink-0">
            <Building2 className="w-4 h-4 text-violet-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-white truncate max-w-[180px]">
              {vendor.company_name}
            </p>
            <p className="text-xs text-slate-600 font-mono truncate">
              {vendor.run_id}
            </p>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-2 text-xs text-slate-500 hidden sm:table-cell">
        {vendor.country ?? "—"}
      </td>
      <td className="py-3.5 px-2">
        <StatusBadge status={vendor.status} size="sm" />
      </td>
      <td className="py-3.5 px-2 hidden md:table-cell">
        {vendor.decision_summary ? (
          <p className="text-xs text-slate-500 truncate max-w-[220px] leading-relaxed">
            {vendor.decision_summary}
          </p>
        ) : (
          <span className="text-xs text-slate-700">—</span>
        )}
      </td>
      <td className="py-3.5 px-2 text-xs text-slate-600 whitespace-nowrap hidden sm:table-cell">
        <div className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          {timeAgo}
        </div>
      </td>
      <td className="py-3.5 pl-2 pr-4">
        <div className="flex items-center justify-end">
          <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-violet-400 transition-colors" />
        </div>
      </td>
    </tr>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [vendors, setVendors] = useState<PaginatedVendors | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [offline, setOffline] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const STATUS_FILTERS = [
    { value: "all", label: "All" },
    { value: "processing", label: "Processing" },
    { value: "pending", label: "Pending" },
    { value: "approved", label: "Approved" },
    { value: "rejected", label: "Rejected" },
    { value: "error", label: "Error" },
  ];

  const loadData = useCallback(
    async (showRefreshing = false) => {
      if (showRefreshing) setRefreshing(true);
      else setLoading(true);

      try {
        const [statsData, vendorsData] = await Promise.all([
          getDashboardStats(),
          getDashboardHistory({
            page,
            page_size: 15,
            status: statusFilter !== "all" ? statusFilter : undefined,
            search: search || undefined,
          }),
        ]);
        setOffline(false);
        setStats(statsData);
        setVendors(vendorsData);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (msg.includes("fetch") || msg.includes("network") || msg.includes("ECONNREFUSED")) {
          setOffline(true);
        }
        console.error("Dashboard load error:", e);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [page, statusFilter, search]
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 10 seconds when there are processing items
  useEffect(() => {
    const hasProcessing = stats?.processing && stats.processing > 0;
    if (!hasProcessing) return;
    const interval = setInterval(() => loadData(true), 10000);
    return () => clearInterval(interval);
  }, [stats?.processing, loadData]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const handleStatusFilter = (status: string) => {
    setStatusFilter(status);
    setPage(1);
  };

  if (loading && !stats) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
          <p className="text-slate-400 text-sm">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (offline) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full card border-amber-500/20 text-center">
          <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7 text-amber-400" />
          </div>
          <h2 className="text-white font-semibold mb-2">Backend Offline</h2>
          <p className="text-slate-400 text-sm mb-2 leading-relaxed">
            Cannot connect to the API server at{" "}
            <code className="text-slate-300 bg-slate-800 px-1 py-0.5 rounded text-xs">
              {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
            </code>
          </p>
          <p className="text-slate-500 text-xs mb-6 leading-relaxed">
            Start the backend with:{" "}
            <code className="text-slate-400 bg-slate-800 px-1 py-0.5 rounded text-xs">
              uvicorn app.main:app --reload
            </code>
          </p>
          <button
            onClick={() => loadData()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600/80 hover:bg-amber-600 text-white text-sm rounded-xl transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const STAT_CARDS = [
    {
      label: "Total Submissions",
      value: stats?.total ?? 0,
      icon: TrendingUp,
      color: "text-violet-400",
      bg: "bg-violet-500/15",
      glow: "shadow-violet-500/20",
      filter: "all",
    },
    {
      label: "Approved",
      value: stats?.approved ?? 0,
      icon: CheckCircle,
      color: "text-emerald-400",
      bg: "bg-emerald-500/15",
      glow: "shadow-emerald-500/20",
      filter: "approved",
    },
    {
      label: "Pending Review",
      value: stats?.pending ?? 0,
      icon: Clock,
      color: "text-amber-400",
      bg: "bg-amber-500/15",
      glow: "shadow-amber-500/20",
      filter: "pending",
    },
    {
      label: "Rejected",
      value: stats?.rejected ?? 0,
      icon: XCircle,
      color: "text-red-400",
      bg: "bg-red-500/15",
      glow: "shadow-red-500/20",
      filter: "rejected",
    },
    {
      label: "Processing",
      value: stats?.processing ?? 0,
      icon: Loader2,
      color: "text-blue-400",
      bg: "bg-blue-500/15",
      glow: "shadow-blue-500/20",
      filter: "processing",
    },
  ];

  return (
    <div className="min-h-screen py-8 px-4">
      {/* Background */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-0 right-1/4 w-[500px] h-[200px] bg-violet-600/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-medium mb-2">
              <LayoutDashboard className="w-3 h-3" />Admin Portal
            </div>
            <div className="flex items-center gap-2.5 mb-1">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center">
                <BarChart3 className="w-4 h-4 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white">Vendor Dashboard</h1>
            </div>
            <p className="text-sm text-slate-500">
              Monitor and manage all vendor submissions
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                await fetch("/api/admin/logout", { method: "POST" });
                router.push("/admin/login");
                router.refresh();
              }}
              className="flex items-center gap-2 px-3 py-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 border border-slate-700/50 text-sm rounded-xl transition-all"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
            <button
              onClick={() => loadData(true)}
              disabled={refreshing}
              className="flex items-center gap-2 px-3 py-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/80 text-slate-400 hover:text-slate-300 text-sm rounded-xl transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin text-violet-400" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button
              onClick={() => router.push("/submit")}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-violet-500/20"
            >
              <Plus className="w-4 h-4" />
              New Submission
            </button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          {STAT_CARDS.map((card) => (
            <StatCard
              key={card.label}
              label={card.label}
              value={card.value}
              icon={card.icon}
              color={card.color}
              bg={card.bg}
              glow={card.glow}
              isActive={statusFilter === card.filter}
              onClick={() => handleStatusFilter(card.filter)}
            />
          ))}
        </div>

        {/* Table Controls */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[200px]">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search by name, email, run ID..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="input-field pl-9 h-9 text-xs"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-2 bg-slate-800/80 border border-slate-700/80 text-slate-400 hover:text-slate-300 text-xs rounded-xl transition-colors"
            >
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => { setSearch(""); setSearchInput(""); setPage(1); }}
                className="px-3 py-2 text-slate-500 hover:text-slate-300 text-xs transition-colors"
              >
                Clear
              </button>
            )}
          </form>

          {/* Status filter pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-slate-600" />
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => handleStatusFilter(f.value)}
                className={`px-2.5 py-1 text-xs rounded-lg transition-all ${
                  statusFilter === f.value
                    ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                    : "bg-slate-800/60 text-slate-500 border border-slate-700/50 hover:text-slate-300"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="card p-0 overflow-hidden">
          {vendors?.items.length === 0 ? (
            <div className="text-center py-16">
              <Building2 className="w-10 h-10 text-slate-700 mx-auto mb-4" />
              <p className="text-slate-500 text-sm">No submissions found</p>
              <p className="text-slate-600 text-xs mt-1">
                {search || statusFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Submit your first vendor to get started"}
              </p>
              <button
                onClick={() => router.push("/submit")}
                className="mt-4 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm rounded-xl transition-colors"
              >
                New Submission
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-800/80">
                    <th className="text-left py-3 pl-4 pr-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Vendor
                    </th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:table-cell">
                      Country
                    </th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-slate-500 uppercase tracking-wider hidden md:table-cell">
                      Decision Summary
                    </th>
                    <th className="text-left py-3 px-2 text-xs font-medium text-slate-500 uppercase tracking-wider hidden sm:table-cell">
                      Submitted
                    </th>
                    <th className="py-3 pl-2 pr-4" />
                  </tr>
                </thead>
                <tbody>
                  {vendors?.items.map((vendor) => (
                    <RunRow
                      key={vendor.id}
                      vendor={vendor}
                      onClick={() => router.push(`/runs/${vendor.run_id}`)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {vendors && vendors.pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/60">
              <p className="text-xs text-slate-500">
                Showing {((page - 1) * 15) + 1}–{Math.min(page * 15, vendors.total)} of {vendors.total} results
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-500 hover:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs text-slate-400 px-2">
                  {page} / {vendors.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(vendors.pages, p + 1))}
                  disabled={page === vendors.pages}
                  className="p-1.5 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-500 hover:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Empty state when no submissions at all */}
        {stats?.total === 0 && (
          <div className="mt-8 card text-center py-12 border-dashed border-slate-700/60">
            <div className="w-14 h-14 rounded-2xl bg-violet-500/10 flex items-center justify-center mx-auto mb-4">
              <Building2 className="w-7 h-7 text-violet-400" />
            </div>
            <h3 className="text-white font-semibold mb-2">No submissions yet</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-xs mx-auto">
              Submit your first vendor for AI-powered validation
            </p>
            <button
              onClick={() => router.push("/submit")}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-colors"
            >
              <Plus className="w-4 h-4" />
              Submit First Vendor
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
