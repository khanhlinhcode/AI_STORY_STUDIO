import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const backend = process.env.BACKEND_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const cookieSecure = process.env.SESSION_COOKIE_SECURE === "true" || (process.env.SESSION_COOKIE_SECURE !== "false" && process.env.NODE_ENV === "production");

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const jar = await cookies();
  const access = jar.get("studio_access")?.value;
  const refreshToken = jar.get("studio_refresh")?.value;
  const workspace = jar.get("studio_workspace")?.value;
  if (!access && !refreshToken) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const headers = new Headers();
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (workspace) headers.set("X-Workspace-ID", workspace);
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const url = new URL(`${backend}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => url.searchParams.append(key, value));
  const method = request.method;
  const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
  let response = await fetch(url, {
    method,
    headers,
    body,
    cache: "no-store",
  });
  let refreshed: { access_token: string; refresh_token: string } | null = null;
  if (response.status === 401 && refreshToken) {
    const refresh = await fetch(`${backend}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    });
    if (refresh.ok) {
      refreshed = await refresh.json();
      headers.set("Authorization", `Bearer ${refreshed?.access_token}`);
      response = await fetch(url, { method, headers, body, cache: "no-store" });
    }
  }
  const result = new NextResponse(response.status === 204 ? null : response.body, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") ?? "application/json" } });
  if (refreshed) {
    result.cookies.set("studio_access", refreshed.access_token, { httpOnly: true, sameSite: "lax", secure: cookieSecure, path: "/", maxAge: 30 * 60 });
    result.cookies.set("studio_refresh", refreshed.refresh_token, { httpOnly: true, sameSite: "lax", secure: cookieSecure, path: "/", maxAge: 7 * 24 * 60 * 60 });
  }
  return result;
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;

