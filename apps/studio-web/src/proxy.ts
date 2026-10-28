import { NextRequest, NextResponse } from "next/server";

const protectedPaths = ["/dashboard", "/projects", "/episodes", "/jobs", "/models", "/assets", "/admin"];

export function proxy(request: NextRequest) {
  const isProtected = protectedPaths.some((path) => request.nextUrl.pathname.startsWith(path));
  const hasSession = request.cookies.has("studio_access") || request.cookies.has("studio_refresh");
  if (isProtected && !hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  if (["/login", "/register"].includes(request.nextUrl.pathname) && hasSession) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };

