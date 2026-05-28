import Link from "next/link";
import {
  ArrowRight,
  Shield,
  Zap,
  BarChart3,
  FileCheck,
  Building2,
  UserCheck,
  LayoutDashboard,
  CheckCircle,
  AlertTriangle,
  Mail,
  GitBranch,
} from "lucide-react";

const VENDOR_FEATURES = [
  {
    icon: FileCheck,
    title: "Smart Form Screening",
    description: "Real-time field validation catches wrong entries before submission — we detect if a company name is entered in a GSTIN field.",
    color: "from-violet-500 to-purple-700",
  },
  {
    icon: Mail,
    title: "Email Notifications",
    description: "Get notified immediately when documents can't be read, with specific guidance on what to fix and how to resubmit.",
    color: "from-amber-500 to-orange-600",
  },
  {
    icon: GitBranch,
    title: "Resubmission Tracking",
    description: "Every resubmission is versioned. See exactly what you improved versus your previous attempt.",
    color: "from-emerald-500 to-green-700",
  },
];

const ADMIN_FEATURES = [
  {
    icon: BarChart3,
    title: "Category Scores",
    description: "Identity, completeness, consistency, and risk scores for every vendor — at a glance.",
    color: "from-blue-500 to-cyan-600",
  },
  {
    icon: Shield,
    title: "Cross-Validation",
    description: "GSTIN ↔ PAN, IFSC ↔ bank name, document vs form data — all cross-checked automatically.",
    color: "from-rose-500 to-red-700",
  },
  {
    icon: Zap,
    title: "Live Pipeline",
    description: "Watch every validation stage execute in real time with Server-Sent Events.",
    color: "from-violet-500 to-purple-700",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden px-4 pt-16 pb-20">
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-violet-600/8 rounded-full blur-3xl" />
        </div>

        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            Powered by Claude AI
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white tracking-tight mb-4 leading-tight">
            Vendor Onboarding{" "}
            <span className="gradient-text">Automated</span>
          </h1>
          <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            AI-powered validation with real-time field screening, cross-document consistency checks,
            OCR quality detection, and full versioned resubmission tracking.
          </p>

          {/* Portal split */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl mx-auto">
            {/* Vendor Portal */}
            <div className="card border-violet-500/20 text-left group hover:border-violet-500/40 transition-all hover:-translate-y-0.5">
              <div className="flex items-center gap-2.5 mb-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center shadow-lg shadow-purple-500/25">
                  <UserCheck className="w-4.5 h-4.5 text-white" />
                </div>
                <div>
                  <p className="text-[10px] text-violet-400 uppercase tracking-wider font-semibold">For Vendors</p>
                  <h3 className="text-white font-semibold text-sm">Vendor Portal</h3>
                </div>
              </div>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                Submit your onboarding application, track its status, and resubmit with fixes if needed.
              </p>
              <div className="flex flex-col gap-2">
                <Link
                  href="/submit"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-violet-500/20"
                >
                  Submit Application
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link
                  href="/vendor"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-sm rounded-xl border border-slate-700/80 transition-all"
                >
                  Track My Application
                </Link>
              </div>
            </div>

            {/* Admin Portal */}
            <div className="card border-blue-500/20 text-left group hover:border-blue-500/40 transition-all hover:-translate-y-0.5">
              <div className="flex items-center gap-2.5 mb-3">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-blue-500/25">
                  <LayoutDashboard className="w-4.5 h-4.5 text-white" />
                </div>
                <div>
                  <p className="text-[10px] text-blue-400 uppercase tracking-wider font-semibold">For Procurement</p>
                  <h3 className="text-white font-semibold text-sm">Admin Portal</h3>
                </div>
              </div>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                Monitor all vendor submissions, review category scores, email logs, and version history.
              </p>
              <div className="flex flex-col gap-2">
                <Link
                  href="/dashboard"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-blue-500/20"
                >
                  Open Dashboard
                  <BarChart3 className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Vendor Features */}
      <section className="px-4 pb-16">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-violet-500/20 flex items-center justify-center">
              <UserCheck className="w-3 h-3 text-violet-400" />
            </div>
            <p className="section-label mb-0">Vendor Experience</p>
          </div>
          <h2 className="text-2xl font-bold text-white mb-6">Smart Guidance At Every Step</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {VENDOR_FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="card hover:border-slate-600/80 transition-all hover:-translate-y-0.5">
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center mb-3 shadow-md`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-white font-semibold text-sm mb-1.5">{f.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{f.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Admin Features */}
      <section className="px-4 pb-16">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-5 h-5 rounded bg-blue-500/20 flex items-center justify-center">
              <LayoutDashboard className="w-3 h-3 text-blue-400" />
            </div>
            <p className="section-label mb-0">Admin Capabilities</p>
          </div>
          <h2 className="text-2xl font-bold text-white mb-6">Enterprise-Grade Validation Intelligence</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {ADMIN_FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="card hover:border-slate-600/80 transition-all hover:-translate-y-0.5">
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${f.color} flex items-center justify-center mb-3 shadow-md`}>
                    <Icon className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="text-white font-semibold text-sm mb-1.5">{f.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{f.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Pipeline steps */}
      <section className="px-4 pb-20">
        <div className="max-w-4xl mx-auto">
          <div className="card glow-purple border-violet-500/20 text-center p-8">
            <p className="section-label">Validation Pipeline</p>
            <h2 className="text-xl font-bold text-white mb-6">12-Stage AI Validation</h2>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                "Intake", "Field Extraction", "Format Check (L1)", "Doc OCR",
                "Cross-Doc Check (L3)", "Data Merge", "Completeness",
                "Consistency", "Credibility", "Decision", "Email Output", "Done"
              ].map((step, i) => (
                <div key={step} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs text-slate-300">
                  <span className="w-4 h-4 rounded-full bg-violet-500/20 text-violet-400 text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                    {i + 1}
                  </span>
                  {step}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
