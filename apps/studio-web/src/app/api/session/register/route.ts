import { NextRequest, NextResponse } from "next/server";

const backend = process.env.BACKEND_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const cookieSecure = process.env.SESSION_COOKIE_SECURE === "true" || (process.env.SESSION_COOKIE_SECURE !== "false" && process.env.NODE_ENV === "production");

export async function POST(request: NextRequest) {
  const response = await fetch(`${backend}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json();
  if (!response.ok) return NextResponse.json(payload, { status: response.status });
  const result = NextResponse.json({ workspace_id: payload.workspace_id });
  result.cookies.set("studio_access", payload.access_token, { httpOnly: true, sameSite: "lax", secure: cookieSecure, path: "/", maxAge: 30 * 60 });
  result.cookies.set("studio_refresh", payload.refresh_token, { httpOnly: true, sameSite: "lax", secure: cookieSecure, path: "/", maxAge: 7 * 24 * 60 * 60 });
  result.cookies.set("studio_workspace", payload.workspace_id, { httpOnly: true, sameSite: "lax", secure: cookieSecure, path: "/", maxAge: 7 * 24 * 60 * 60 });
  return result;
}
