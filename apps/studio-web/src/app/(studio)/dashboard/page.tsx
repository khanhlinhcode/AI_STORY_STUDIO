"use client";

import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Film,
  Layers3,
  Plus,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { EmptyState } from "@/components/empty-state";
import { PageHeading } from "@/components/page-heading";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api-client";
import type { Job, Project } from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<Project[]>("/projects"),
  });
  const startFromNews = useMutation({
    mutationFn: async () => {
      const project =
        projects.data?.find(
          (item) => item.title === "Khám phá khoa học & thiên nhiên",
        ) ??
        (await apiFetch<Project>("/projects", {
          method: "POST",
          body: JSON.stringify({ title: "Khám phá khoa học & thiên nhiên" }),
        }));
      if (!project.autopilot_enabled) {
        await apiFetch(`/projects/${project.id}/autopilot`, {
          method: "PATCH",
          body: JSON.stringify({ enabled: true }),
        });
      }
      await apiFetch(`/projects/${project.id}/autopilot/run`, {
        method: "POST",
        body: "{}",
      });
      return project.id;
    },
    onSuccess: (projectId) => router.push(`/projects/${projectId}`),
  });
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiFetch<Job[]>("/jobs"),
    refetchInterval: 5000,
  });
  const running =
    jobs.data?.filter((job) =>
      ["queued", "claimed", "running"].includes(job.status),
    ).length ?? 0;
  const episodeJobs =
    jobs.data?.filter((job) => job.job_kind === "episode") ?? [];
  const completed = episodeJobs.filter(
    (job) => job.status === "completed",
  ).length;
  return (
    <>
      <PageHeading
        eyebrow="Production overview"
        title="Chào mừng đến xưởng truyện."
        description="Theo dõi mọi tập phim từ khám phá mới đến bản xem thử."
        action={
          <div className="flex flex-wrap gap-2">
            <button
              className="button-primary"
              onClick={() => startFromNews.mutate()}
              disabled={startFromNews.isPending || projects.isLoading}
            >
              <Sparkles size={17} />
              {startFromNews.isPending
                ? "Đang lấy tin…"
                : "Bật Autopilot & tạo video"}
            </button>
            <Link href="/projects" className="button-secondary">
              <Plus size={17} />
              Dự án
            </Link>
          </div>
        }
      />
      {startFromNews.error && (
        <p role="alert" className="mb-5 text-sm text-red-700">
          {startFromNews.error.message}
        </p>
      )}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Dự án",
            value: projects.data?.length ?? "—",
            hint: "đang hoạt động",
            icon: Layers3,
            tone: "bg-teal-500/10 text-teal-600",
          },
          {
            label: "Đang sản xuất",
            value: running,
            hint: "job trong pipeline",
            icon: Sparkles,
            tone: "bg-indigo-50 text-indigo-600",
          },
          {
            label: "Video hoàn tất",
            value: completed,
            hint: "sẵn sàng kiểm tra",
            icon: Film,
            tone: "bg-orange-50 text-orange-600",
          },
          {
            label: "Tỷ lệ hoàn tất",
            value: episodeJobs.length
              ? `${Math.round((completed / episodeJobs.length) * 100)}%`
              : "—",
            hint: "các job tập phim",
            icon: CheckCircle2,
            tone: "bg-emerald-50 text-emerald-600",
          },
        ].map(({ label, value, hint, icon: Icon, tone }) => (
          <article key={label} className="panel p-5">
            <div
              className={`grid h-10 w-10 place-items-center rounded-xl ${tone}`}
            >
              <Icon size={19} />
            </div>
            <p className="mt-5 text-sm font-bold text-slate-500">{label}</p>
            <p className="display mt-1 text-4xl font-bold">{value}</p>
            <p className="mt-1 text-xs text-slate-400">{hint}</p>
          </article>
        ))}
      </section>
      <section className="mt-7 grid gap-7 xl:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-extrabold">Luồng sản xuất gần đây</h2>
            <Link
              href="/jobs"
              className="flex items-center gap-1 text-sm font-bold text-teal-600"
            >
              Xem tất cả <ArrowRight size={15} />
            </Link>
          </div>
          {jobs.isLoading ? (
            <div className="panel h-64 animate-pulse" />
          ) : jobs.data?.length ? (
            <div className="panel divide-y divide-[#ece8df] overflow-hidden">
              {jobs.data.slice(0, 6).map((job) => (
                <Link
                  href={`/jobs/${job.id}`}
                  key={job.id}
                  className="flex items-center gap-4 p-4 hover:bg-white"
                >
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100">
                    <Film size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-extrabold">
                      Episode {job.episode_id.slice(0, 8)}
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      {job.execution_mode} · rev {job.snapshot_revision}
                    </p>
                  </div>
                  <StatusBadge status={job.status} />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Chưa có job nào"
              message="Tạo dự án và một tập truyện để khởi động pipeline đầu tiên."
            />
          )}
        </div>
        <div>
          <h2 className="mb-4 text-lg font-extrabold">Hôm nay trong studio</h2>
          <div className="panel overflow-hidden">
            <div className="bg-ink p-5 text-white">
              <p className="eyebrow !text-teal-500">Daily rhythm</p>
              <p className="display mt-2 text-2xl font-bold">
                Một câu chuyện hay bắt đầu từ nhịp đều đặn.
              </p>
            </div>
            <div className="grid gap-4 p-5">
              {[
                {
                  icon: Clock3,
                  title: "Lịch mẫu 07:00",
                  text: "Bật workflow n8n sau khi cấu hình Google Sheets",
                },
                {
                  icon: Sparkles,
                  title: "Quality gate",
                  text: "Kiểm tra codec, phụ đề, thời lượng; cần người duyệt nội dung",
                },
                {
                  icon: Film,
                  title: "Manual publish",
                  text: "Bạn vẫn là người bấm nút đăng",
                },
              ].map(({ icon: Icon, title, text }) => (
                <div key={title} className="flex gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-teal-500/10 text-teal-600">
                    <Icon size={16} />
                  </span>
                  <div>
                    <p className="text-sm font-extrabold">{title}</p>
                    <p className="text-xs leading-5 text-slate-500">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
