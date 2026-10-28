"use client";

import { ArrowRight, BookOpen, Plus, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { EmptyState } from "@/components/empty-state";
import { PageHeading } from "@/components/page-heading";
import { apiFetch } from "@/lib/api-client";
import { useProjects } from "@/lib/queries";
import type { Project } from "@/lib/types";

export default function ProjectsPage() {
  const projects = useProjects(); const client = useQueryClient(); const [open, setOpen] = useState(false); const [search, setSearch] = useState("");
  const create = useMutation({ mutationFn: (title: string) => apiFetch<Project>("/projects", { method: "POST", body: JSON.stringify({ title, locale: "vi", audience: "children-6-10", style_profile: { visual: "Vietnamese 2D storybook" } }) }), onSuccess: () => { client.invalidateQueries({ queryKey: ["projects"] }); setOpen(false); } });
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); create.mutate(String(new FormData(event.currentTarget).get("title"))); }
  const filtered = projects.data?.filter((item) => item.title.toLocaleLowerCase("vi").includes(search.toLocaleLowerCase("vi")));
  return <>
    <PageHeading eyebrow="Project library" title="Tủ truyện" description="Mỗi dự án giữ một thế giới nhân vật, phong cách hình ảnh và lịch sử sản xuất riêng." action={<button onClick={() => setOpen(true)} className="button-primary"><Plus size={17}/>Dự án mới</button>}/>
    <div className="mb-5 flex max-w-md items-center gap-2 rounded-xl border border-[#ddd8ce] bg-white px-3"><Search size={17} className="text-slate-400"/><input value={search} onChange={(e) => setSearch(e.target.value)} className="w-full border-0 bg-transparent py-3 text-sm outline-none" placeholder="Tìm dự án…" aria-label="Tìm dự án"/></div>
    {projects.isLoading ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{[1,2,3].map((value) => <div key={value} className="panel h-56 animate-pulse"/>)}</div> : filtered?.length ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{filtered.map((project, index) => <Link key={project.id} href={`/projects/${project.id}`} className="panel group overflow-hidden transition hover:-translate-y-1 hover:shadow-card"><div className={`h-28 ${["bg-gradient-to-br from-teal-500 to-cyan-300", "bg-gradient-to-br from-orange-400 to-rose-300", "bg-gradient-to-br from-indigo-500 to-violet-300"][index % 3]} p-5`}><span className="grid h-11 w-11 place-items-center rounded-xl bg-white/90 text-ink"><BookOpen size={20}/></span></div><div className="p-5"><p className="text-xs font-extrabold uppercase tracking-wider text-slate-400">{project.audience}</p><h2 className="display mt-2 text-2xl font-bold">{project.title}</h2><div className="mt-5 flex items-center justify-between text-sm font-bold text-teal-600"><span>{project.locale.toUpperCase()} · v{project.version}</span><ArrowRight size={17} className="transition group-hover:translate-x-1"/></div></div></Link>)}</div> : <EmptyState title="Tủ truyện đang trống" message="Tạo dự án đầu tiên để định nghĩa nhân vật, phong cách và các tập phim." action={<button onClick={() => setOpen(true)} className="button-primary"><Plus size={17}/>Tạo dự án</button>}/>} 
    {open && <div role="dialog" aria-modal="true" aria-labelledby="new-project-title" className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4"><form onSubmit={submit} className="panel w-full max-w-md p-6"><p className="eyebrow">New world</p><h2 id="new-project-title" className="display mt-2 text-3xl font-bold">Tạo dự án truyện</h2><label className="field-label mt-6">Tên dự án<input name="title" className="field" required autoFocus placeholder="Ví dụ: Khu rừng của Mimi"/></label>{create.error && <p className="mt-3 text-sm font-bold text-red-600">{create.error.message}</p>}<div className="mt-6 flex justify-end gap-2"><button type="button" onClick={() => setOpen(false)} className="button-secondary">Hủy</button><button disabled={create.isPending} className="button-primary">{create.isPending ? "Đang tạo…" : "Tạo dự án"}</button></div></form></div>}
  </>;
}

