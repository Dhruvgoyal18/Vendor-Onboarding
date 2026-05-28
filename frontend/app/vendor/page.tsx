"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, UserCheck, ArrowRight, Building2 } from "lucide-react";

export default function VendorLookupPage() {
  const router = useRouter();
  const [runId, setRunId] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = runId.trim();
    if (!clean) { setError("Please enter your Application ID"); return; }
    if (!clean.startsWith("vnd_")) { setError("Application IDs start with 'vnd_' — check your confirmation email"); return; }
    router.push(`/vendor/${clean}`);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-violet-600/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-500/25">
            <UserCheck className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2">Track Your Application</h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            Enter the Application ID you received after submitting your vendor onboarding form.
          </p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-2">
                Application ID
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="text"
                  className="input-field pl-9 font-mono"
                  placeholder="vnd_20260526_abc12345"
                  value={runId}
                  onChange={(e) => { setRunId(e.target.value); setError(""); }}
                  autoFocus
                />
              </div>
              {error && (
                <p className="text-xs text-red-400 mt-1.5">{error}</p>
              )}
              <p className="text-xs text-slate-600 mt-1.5">
                Find this in your submission confirmation email.
              </p>
            </div>

            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-violet-500/20"
            >
              View Application Status
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>

        <div className="mt-6 text-center space-y-3">
          <p className="text-xs text-slate-600">Haven't submitted yet?</p>
          <a
            href="/submit"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-800/60 hover:bg-slate-700/60 text-slate-400 hover:text-slate-300 text-sm rounded-xl border border-slate-700/50 transition-all"
          >
            <Building2 className="w-4 h-4" />
            Submit New Application
          </a>
          <p className="text-xs text-slate-600">
            Have an account?{" "}
            <a href="/vendor/login" className="text-violet-400 hover:text-violet-300 transition-colors">
              Sign in to see all your applications
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
