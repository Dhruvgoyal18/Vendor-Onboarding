import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("vendor_refresh_token")?.value;

  if (refreshToken) {
    await fetch(`${API_URL}/api/auth/vendor/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => {});
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.delete("vendor_access_token");
  response.cookies.delete("vendor_refresh_token");
  return response;
}
