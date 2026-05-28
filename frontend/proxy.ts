import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

const JWT_SECRET = new TextEncoder().encode(
  process.env.JWT_SECRET || "change-me-in-production-use-a-long-random-string"
);
const API_URL = process.env.API_URL || "http://localhost:8000";
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;

async function verifyToken(token: string, expectedRole: string): Promise<boolean> {
  try {
    const { payload } = await jwtVerify(token, JWT_SECRET);
    return payload.role === expectedRole && payload.type === "access";
  } catch {
    return false;
  }
}

async function refreshTokens(
  refreshToken: string,
  role: "admin" | "vendor"
): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const res = await fetch(`${API_URL}/api/auth/${role}/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function setTokenCookies(
  response: NextResponse,
  role: "admin" | "vendor",
  accessToken: string,
  refreshToken: string
): void {
  response.cookies.set(`${role}_access_token`, accessToken, {
    httpOnly: false,
    sameSite: "strict",
    maxAge: ACCESS_MAX_AGE,
    path: "/",
  });
  response.cookies.set(`${role}_refresh_token`, refreshToken, {
    httpOnly: true,
    sameSite: "strict",
    maxAge: REFRESH_MAX_AGE,
    path: "/",
  });
}

async function handleProtectedRoute(
  request: NextRequest,
  role: "admin" | "vendor",
  loginPath: string
): Promise<NextResponse> {
  const { pathname } = request.nextUrl;
  const accessToken = request.cookies.get(`${role}_access_token`)?.value;
  const refreshToken = request.cookies.get(`${role}_refresh_token`)?.value;

  // Valid access token → proceed
  if (accessToken && (await verifyToken(accessToken, role))) {
    return NextResponse.next();
  }

  // Expired/missing access token → try refresh
  if (refreshToken) {
    const tokens = await refreshTokens(refreshToken, role);
    if (tokens) {
      const response = NextResponse.next();
      setTokenCookies(response, role, tokens.access_token, tokens.refresh_token);
      return response;
    }
    // Refresh failed — clear stale cookies and redirect
    const loginUrl = new URL(loginPath, request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.delete(`${role}_access_token`);
    response.cookies.delete(`${role}_refresh_token`);
    return response;
  }

  // No tokens → redirect to login
  const loginUrl = new URL(loginPath, request.url);
  loginUrl.searchParams.set("redirect", pathname);
  return NextResponse.redirect(loginUrl);
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/dashboard") || pathname.startsWith("/runs")) {
    return handleProtectedRoute(request, "admin", "/admin/login");
  }

  if (pathname.startsWith("/vendor/me")) {
    return handleProtectedRoute(request, "vendor", "/vendor/login");
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/runs/:path*", "/vendor/me/:path*"],
};
