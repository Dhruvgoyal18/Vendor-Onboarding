"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMySubmissions } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import {
  Building2,
  Loader2,
  LogOut,
  Plus,
  ExternalLink,
  Clock,
  RefreshCw,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

type Submission = {
  run_id: string;
  company_name: string;
  country: string;
  status: string;
  risk_level: string | null;
  created_at: string;
  decided_at: string | null;
  version_number: number;
};

export default function VendorPortalPage() {
  const router = useRouter();
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getMySubmissions();
      setSubmissions(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleLogout = async () => {
    await fetch("/api/vendor/logout", { method: "POST" });
    router.push("/vendor/login");
    router.refresh();
  };

  return (
    <div className="min-h-screen py-10 px-4">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">My Applications</h1>
            <p className="text-sm text-slate-500 mt-0.5">All your vendor submissions</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={load}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <a
              href="/submit"
              className="flex items-center gap-1.5 px-3 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all"
            >
              <Plus className="w-4 h-4" />
              New Application
            </a>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 text-sm rounded-xl border border-slate-700/50 transition-all"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
          </div>
        ) : error ? (
          <div className="card text-center py-10">
            <p className="text-red-400 text-sm">{error}</p>
            <button onClick={load} className="mt-4 text-xs text-violet-400 hover:text-violet-300">
              Try again
            </button>
          </div>
        ) : submissions.length === 0 ? (
          <div className="card text-center py-12">
            <Building2 className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm font-medium mb-1">No applications yet</p>
            <p className="text-slate-600 text-xs mb-6">Submit your first vendor application to get started.</p>
            <a
              href="/submit"
              className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all"
            >
              <Plus className="w-4 h-4" />
              Submit Application
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {submissions.map((s) => (
              <div
                key={s.run_id}
                className="card hover:border-slate-600/50 transition-colors cursor-pointer"
                onClick={() => router.push(`/vendor/${s.run_id}`)}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-violet-500/15 flex items-center justify-center flex-shrink-0">
                      <Building2 className="w-4 h-4 text-violet-400" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white truncate">{s.company_name}</p>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">{s.run_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    {s.version_number > 1 && (
                      <span className="text-xs px-2 py-0.5 bg-slate-700/60 text-slate-400 rounded-full">
                        v{s.version_number}
                      </span>
                    )}
                    <StatusBadge status={s.status} />
                    <ExternalLink className="w-3.5 h-3.5 text-slate-600" />
                  </div>
                </div>
                <div className="mt-3 pt-3 border-t border-slate-700/50 flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    Submitted {formatDistanceToNow(new Date(s.created_at), { addSuffix: true })}
                  </span>
                  {s.decided_at && (
                    <span>
                      Decided {formatDistanceToNow(new Date(s.decided_at), { addSuffix: true })}
                    </span>
                  )}
                  <span className="ml-auto">{s.country}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
