import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("vendor_refresh_token")?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  const res = await fetch(`${API_URL}/api/auth/vendor/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    const response = NextResponse.json({ error: "Refresh failed" }, { status: 401 });
    response.cookies.delete("vendor_access_token");
    response.cookies.delete("vendor_refresh_token");
    return response;
  }

  const { access_token, refresh_token } = await res.json();
  const response = NextResponse.json({ ok: true });

  response.cookies.set("vendor_access_token", access_token, {
    httpOnly: false,
    sameSite: "strict",
    maxAge: ACCESS_MAX_AGE,
    path: "/",
  });
  response.cookies.set("vendor_refresh_token", refresh_token, {
    httpOnly: true,
    sameSite: "strict",
    maxAge: REFRESH_MAX_AGE,
    path: "/",
  });

  return response;
}
