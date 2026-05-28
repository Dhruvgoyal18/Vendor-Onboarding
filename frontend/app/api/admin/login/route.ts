import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";
const ACCESS_MAX_AGE = 60 * 15;        // 15 min
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export async function POST(request: NextRequest) {
  const body = await request.json();

  const res = await fetch(`${API_URL}/api/auth/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json({ error: err.detail }, { status: res.status });
  }

  const { access_token, refresh_token } = await res.json();
  const response = NextResponse.json({ ok: true });

  // Access token readable by JS (for Bearer auth to backend API)
  response.cookies.set("admin_access_token", access_token, {
    httpOnly: false,
    sameSite: "strict",
    maxAge: ACCESS_MAX_AGE,
    path: "/",
  });
  // Refresh token httpOnly — only readable by server-side routes/middleware
  response.cookies.set("admin_refresh_token", refresh_token, {
    httpOnly: true,
    sameSite: "strict",
    maxAge: REFRESH_MAX_AGE,
    path: "/",
  });

  return response;
}
