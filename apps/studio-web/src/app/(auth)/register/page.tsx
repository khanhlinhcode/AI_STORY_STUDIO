"use client";

import { BookOpenText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const fields = new FormData(event.currentTarget);
    const workspaceName = String(fields.get("workspace_name") ?? "").trim();
    const slug = workspaceName
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .replace(/Đ/g, "D")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    const response = await fetch("/api/session/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: fields.get("email"),
        password: fields.get("password"),
        display_name: fields.get("display_name"),
        workspace_name: workspaceName,
        workspace_slug: slug,
      }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      setError(typeof body.detail === "string" ? body.detail : "Không thể tạo tài khoản. Hãy kiểm tra thông tin và tên workspace.");
      setLoading(false);
      return;
    }
    router.replace("/dashboard");
    router.refresh();
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f4f1eb] p-6">
      <form onSubmit={submit} className="panel w-full max-w-lg p-7 sm:p-10">
        <div className="flex items-center gap-3 font-extrabold text-ink"><BookOpenText size={24} /> AI Story Studio</div>
        <p className="eyebrow mt-8">Bắt đầu</p>
        <h1 className="display mt-2 text-4xl font-bold">Tạo xưởng truyện</h1>
        <div className="mt-7 grid gap-4">
          <label className="field-label">Tên của bạn<input className="field" name="display_name" required maxLength={120} /></label>
          <label className="field-label">Email<input className="field" name="email" type="email" autoComplete="email" required /></label>
          <label className="field-label">Tên workspace<input className="field" name="workspace_name" required minLength={3} maxLength={80} placeholder="Xưởng truyện của Linh" /></label>
          <label className="field-label">Mật khẩu<input className="field" name="password" type="password" autoComplete="new-password" required minLength={10} /></label>
        </div>
        {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button className="button-primary mt-6 w-full" disabled={loading}>{loading ? "Đang tạo…" : "Tạo tài khoản"}</button>
        <p className="mt-5 text-center text-sm text-slate-500">Đã có tài khoản? <Link className="font-bold text-teal-700" href="/login">Đăng nhập</Link></p>
      </form>
    </main>
  );
}
