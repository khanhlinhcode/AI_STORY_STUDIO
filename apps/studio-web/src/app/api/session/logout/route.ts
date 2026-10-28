import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  for (const name of ["studio_access", "studio_refresh", "studio_workspace"]) response.cookies.delete(name);
  return response;
}

