"use client";

import { Archive, BookOpenText, BriefcaseBusiness, CircleGauge, Cpu, LayoutDashboard, LogOut, PanelLeft, Settings2 } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

const navigation = [
  { href: "/dashboard", label: "Tổng quan", icon: LayoutDashboard },
  { href: "/projects", label: "Dự án", icon: BookOpenText },
  { href: "/jobs", label: "Công việc", icon: BriefcaseBusiness },
  { href: "/assets", label: "Tài nguyên", icon: Archive },
  { href: "/models", label: "Mô hình", icon: Cpu },
  { href: "/admin", label: "Vận hành", icon: Settings2 },
];

export function StudioShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const [open, setOpen] = useState(false);
  async function logout() { await fetch("/api/session/logout", { method: "POST" }); router.replace("/login"); router.refresh(); }
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      <aside className={`${open ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-40 flex w-[248px] flex-col border-r border-white/10 bg-ink p-4 text-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0`}>
        <Link href="/dashboard" className="flex items-center gap-3 px-2 py-3 font-extrabold"><span className="grid h-10 w-10 place-items-center rounded-xl bg-white text-ink"><BookOpenText size={20}/></span><span>Story Studio</span></Link>
        <div className="mx-2 mt-6 rounded-xl border border-white/10 bg-white/5 p-3"><p className="text-[10px] font-bold uppercase tracking-[.14em] text-slate-400">Workspace</p><p className="mt-1 truncate text-sm font-bold">Xưởng truyện của tôi</p></div>
        <nav aria-label="Điều hướng chính" className="mt-6 grid gap-1">
          {navigation.map(({ href, label, icon: Icon }) => { const active = pathname.startsWith(href); return <Link key={href} href={href} onClick={() => setOpen(false)} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${active ? "bg-white text-ink" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}><Icon size={18}/>{label}{active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-coral"/>}</Link>; })}
        </nav>
        <div className="mt-auto rounded-xl bg-teal-500/15 p-3"><div className="flex items-center gap-2 text-sm font-bold text-teal-500"><CircleGauge size={16}/>Hệ thống sẵn sàng</div><p className="mt-1 text-xs leading-5 text-slate-400">Fake adapter · Local mode</p></div>
        <button onClick={logout} className="mt-3 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-400 hover:bg-white/10 hover:text-white"><LogOut size={18}/>Đăng xuất</button>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-16 items-center border-b border-[#e7e3da] bg-canvas/90 px-4 backdrop-blur-xl sm:px-7"><button onClick={() => setOpen(true)} aria-label="Mở menu" className="mr-3 rounded-lg p-2 lg:hidden"><PanelLeft/></button><div><p className="text-xs font-bold text-slate-400">AI STORY STUDIO</p><p className="text-sm font-bold">Production workspace</p></div><div className="ml-auto flex items-center gap-3"><span className="hidden rounded-full bg-white px-3 py-1.5 text-xs font-bold text-slate-500 shadow-sm sm:block">Automation mode</span><span className="grid h-9 w-9 place-items-center rounded-full bg-coral text-sm font-black text-white">LS</span></div></header>
        <main className="p-4 sm:p-7 xl:p-9">{children}</main>
      </div>
      {open && <button aria-label="Đóng menu" onClick={() => setOpen(false)} className="fixed inset-0 z-30 bg-black/40 lg:hidden"/>}
    </div>
  );
}

