"use client";

import { ArrowRight, BriefcaseBusiness } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/empty-state";
import { PageHeading } from "@/components/page-heading";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api-client";
import type { Job } from "@/lib/types";

export default function JobsPage() {
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => apiFetch<Job[]>("/jobs"), refetchInterval: 5000 });
  return <><PageHeading eyebrow="Job center" title="Luồng công việc" description="Quan sát tiến độ, đọc lỗi có ngữ cảnh và chỉ retry đúng bước gặp sự cố."/>{jobs.data?.length ? <div className="panel overflow-hidden divide-y divide-[#ece8df]">{jobs.data.map((job) => <Link href={`/jobs/${job.id}`} key={job.id} className="group flex items-center gap-4 p-5 hover:bg-white"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-600"><BriefcaseBusiness size={20}/></span><div className="min-w-0 flex-1"><p className="font-extrabold">Job {job.id.slice(0,8)}</p><p className="mt-1 text-xs text-slate-400">Episode {job.episode_id.slice(0,8)} · {job.execution_mode}</p></div><StatusBadge status={job.status}/><ArrowRight size={17} className="text-slate-300 transition group-hover:translate-x-1"/></Link>)}</div> : <EmptyState title="Hàng đợi đang yên" message="Khi bạn bấm Sản xuất trong storyboard, job sẽ xuất hiện tại đây."/>}</>;
}

