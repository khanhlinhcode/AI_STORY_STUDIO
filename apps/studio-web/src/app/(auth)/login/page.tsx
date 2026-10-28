"use client";

import { BookOpenText, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    const data = new FormData(event.currentTarget);
    const response = await fetch("/api/session/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
    if (!response.ok) { const payload = await response.json(); setError(payload.detail ?? "Đăng nhập không thành công"); setLoading(false); return; }
    const next = new URLSearchParams(window.location.search).get("next");
    router.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard"); router.refresh();
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_.9fr]">
      <section className="relative hidden overflow-hidden bg-ink p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full bg-teal-500/30 blur-3xl" />
        <div className="relative flex items-center gap-3 font-extrabold"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-ink"><BookOpenText size={21}/></span>AI Story Studio</div>
        <div className="relative max-w-xl">
          <p className="eyebrow !text-teal-500">Local-first production</p>
          <h1 className="display mt-4 text-6xl leading-[.98]">Mỗi ý tưởng nhỏ, một thế giới dịu dàng.</h1>
          <p className="mt-6 max-w-lg text-lg leading-8 text-slate-300">Viết, dựng storyboard, tạo giọng kể và xuất video truyện thiếu nhi trong một quy trình có thể kiểm soát.</p>
        </div>
        <div className="relative flex gap-6 text-sm text-slate-400"><span>Vietnamese-first</span><span>•</span><span>Private by design</span><span>•</span><span>Automation ready</span></div>
      </section>
      <section className="flex items-center justify-center p-6 sm:p-12">
        <form onSubmit={submit} className="panel w-full max-w-md p-7 sm:p-10">
          <span className="mb-8 grid h-12 w-12 place-items-center rounded-2xl bg-teal-500/10 text-teal-600"><Sparkles size={22}/></span>
          <p className="eyebrow">Welcome back</p>
          <h2 className="display mt-2 text-4xl font-bold">Vào xưởng truyện</h2>
          <p className="mt-3 text-sm leading-6 text-slate-500">Đăng nhập để tiếp tục sản xuất truyện.</p>
          <div className="mt-8 grid gap-5">
            <label className="field-label">Email<input className="field" name="email" type="email" autoComplete="email" required placeholder="ban@studio.vn"/></label>
            <label className="field-label">Mật khẩu<input className="field" name="password" type="password" autoComplete="current-password" required/></label>
          </div>
          {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</p>}
          <button className="button-primary mt-6 w-full" disabled={loading}>{loading ? "Đang mở studio…" : "Đăng nhập"}</button>
          <p className="mt-5 text-center text-sm text-slate-500">Chưa có tài khoản? <Link className="font-bold text-teal-700" href="/register">Tạo workspace</Link></p>
          <p className="mt-5 text-center text-xs leading-5 text-slate-400">Dữ liệu và model của bạn không được gửi tới dịch vụ AI bên thứ ba khi chạy ở chế độ local.</p>
        </form>
      </section>
    </main>
  );
}

