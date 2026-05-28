import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Building2, LayoutDashboard, UserCheck, LogOut } from "lucide-react";
import { cookies } from "next/headers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VendorAI — Intelligent Vendor Onboarding",
  description: "AI-powered vendor onboarding and procurement validation system.",
};

async function AdminNav() {
  const cookieStore = await cookies();
  const isLoggedIn =
    cookieStore.get("admin_session")?.value ===
    process.env.ADMIN_SESSION_SECRET;

  if (isLoggedIn) {
    return (
      <div className="flex items-center gap-1 pl-1">
        <span className="text-[10px] text-slate-600 uppercase tracking-wider font-medium hidden sm:block">
          Admin
        </span>
        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/60 rounded-lg transition-all"
        >
          <LayoutDashboard className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Dashboard</span>
        </Link>
        <form action="/api/admin/logout" method="POST">
          <button
            type="submit"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 rounded-lg transition-all"
            title="Sign out of admin"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 pl-1">
      <span className="text-[10px] text-slate-600 uppercase tracking-wider font-medium hidden sm:block">
        Admin
      </span>
      <Link
        href="/admin/login"
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/60 rounded-lg transition-all"
      >
        <LayoutDashboard className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Dashboard</span>
      </Link>
    </div>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${inter.className} bg-slate-950 text-slate-100 min-h-screen`}
      >
        <nav className="fixed top-0 left-0 right-0 z-50 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-xl">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14">
              <Link href="/" className="flex items-center gap-2.5 group">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center shadow-lg shadow-purple-500/25">
                  <Building2 className="w-3.5 h-3.5 text-white" />
                </div>
                <span className="font-semibold text-white">VendorAI</span>
              </Link>

              <div className="flex items-center gap-1">
                {/* Vendor side */}
                <div className="flex items-center gap-1 border-r border-slate-700/60 pr-3 mr-1">
                  <span className="text-[10px] text-slate-600 uppercase tracking-wider font-medium hidden sm:block">
                    Vendor
                  </span>
                  <Link
                    href="/vendor"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800/60 rounded-lg transition-all"
                  >
                    <UserCheck className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">My Application</span>
                    <span className="sm:hidden">Portal</span>
                  </Link>
                  <Link
                    href="/submit"
                    className="px-3 py-1.5 text-sm font-medium bg-violet-600 hover:bg-violet-500 text-white rounded-lg transition-all shadow-lg shadow-violet-500/20"
                  >
                    Apply
                  </Link>
                </div>

                {/* Admin side — reads cookie server-side */}
                <AdminNav />
              </div>
            </div>
          </div>
        </nav>

        <main className="pt-14 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
