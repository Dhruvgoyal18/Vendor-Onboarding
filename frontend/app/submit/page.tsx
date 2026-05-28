import { Suspense } from "react";
import SubmissionForm from "@/components/SubmissionForm";
import { Sparkles, Loader2 } from "lucide-react";

export default function SubmitPage() {
  return (
    <div className="min-h-screen py-10 px-4">
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-violet-600/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300 text-xs font-medium mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered Validation
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">Vendor Application</h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            Fill in your company details and upload the required documents. Our AI pipeline will
            validate everything automatically and notify you of the outcome.
          </p>
        </div>

        <div className="flex items-center gap-2 mb-8 p-3 rounded-xl bg-slate-800/40 border border-slate-700/50 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-violet-500/20 text-violet-400 font-semibold flex items-center justify-center">1</span>
            <span className="text-slate-400">Fill form</span>
          </div>
          <div className="flex-1 h-px bg-slate-700/60" />
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-slate-700 text-slate-500 font-semibold flex items-center justify-center">2</span>
            <span>AI validates</span>
          </div>
          <div className="flex-1 h-px bg-slate-700/60" />
          <div className="flex items-center gap-1.5">
            <span className="w-5 h-5 rounded-full bg-slate-700 text-slate-500 font-semibold flex items-center justify-center">3</span>
            <span>Decision</span>
          </div>
        </div>

        <Suspense fallback={
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
          </div>
        }>
          <SubmissionForm />
        </Suspense>
      </div>
    </div>
  );
}
