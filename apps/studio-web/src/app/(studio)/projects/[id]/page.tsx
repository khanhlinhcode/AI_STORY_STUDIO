"use client";

import {
  ArrowLeft,
  ExternalLink,
  Film,
  Plus,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EmptyState } from "@/components/empty-state";
import { PageHeading } from "@/components/page-heading";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api-client";
import type { Episode, Project } from "@/lib/types";

interface SourcePreview {
  title: string;
  summary: string;
  source_url: string;
  published_at: string;
  already_used: boolean;
}

interface SourceStory {
  id: string;
  title: string;
  source_url: string;
  published_at: string;
  status: string;
  error_message: string | null;
  episode_id: string | null;
  job_id: string | null;
  job_status: string | null;
  model_snapshot: { story_model: string; media_backend: string };
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const project = useQuery({
    queryKey: ["project", id],
    queryFn: () => apiFetch<Project>(`/projects/${id}`),
  });
  const episodes = useQuery({
    queryKey: ["project", id, "episodes"],
    queryFn: () => apiFetch<Episode[]>(`/projects/${id}/episodes`),
  });
  const preview = useQuery({
    queryKey: ["project", id, "autopilot", "preview"],
    queryFn: () =>
      apiFetch<SourcePreview[]>(`/projects/${id}/autopilot/preview`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const sources = useQuery({
    queryKey: ["project", id, "autopilot", "sources"],
    queryFn: () => apiFetch<SourceStory[]>(`/projects/${id}/autopilot/sources`),
    refetchInterval: 5000,
  });
  const latestCandidate = preview.data?.find((item) => !item.already_used);
  const runAutopilot = useMutation({
    mutationFn: () =>
      apiFetch<{ source_id: string }>(`/projects/${id}/autopilot/run`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["project", id, "autopilot", "sources"],
      });
      queryClient.invalidateQueries({
        queryKey: ["project", id, "autopilot", "preview"],
      });
    },
  });
  const toggleAutopilot = useMutation({
    mutationFn: (enabled: boolean) =>
      apiFetch(`/projects/${id}/autopilot`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["project", id] }),
  });
  const retrySource = useMutation({
    mutationFn: (sourceId: string) =>
      apiFetch(`/projects/${id}/autopilot/retry/${sourceId}`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["project", id, "autopilot", "sources"],
      }),
  });
  const create = useMutation({
    mutationFn: async (payload: { topic: string; mode: string }) => {
      const episode = await apiFetch<Episode>(`/projects/${id}/episodes`, {
        method: "POST",
        body: JSON.stringify({
          title: payload.topic,
          topic: payload.topic,
          execution_mode: payload.mode,
          aspect_ratio: "9:16",
        }),
      });
      await apiFetch(`/episodes/${episode.id}/script/generate`, {
        method: "POST",
        body: JSON.stringify({
          topic: payload.topic,
          style: "Vietnamese 2D storybook, warm paper texture",
        }),
      });
      return episode;
    },
    onSuccess: (episode) => {
      queryClient.invalidateQueries({ queryKey: ["project", id, "episodes"] });
      router.push(`/projects/${id}/episodes/${episode.id}/storyboard`);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      topic: String(data.get("topic")),
      mode: String(data.get("mode")),
    });
  }
  return (
    <>
      <Link
        href="/projects"
        className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-ink"
      >
        <ArrowLeft size={16} /> Tủ truyện
      </Link>
      <PageHeading
        eyebrow="Project"
        title={project.data?.title ?? "Đang tải…"}
        description="Tự lấy khám phá khoa học mới và biến thành truyện sáu cảnh, hoặc tự nhập một chủ đề."
        action={
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => runAutopilot.mutate()}
              disabled={runAutopilot.isPending}
              className="button-primary"
            >
              <Sparkles size={17} />
              {runAutopilot.isPending
                ? "Đang tìm bài mới…"
                : "Lấy tin mới & sản xuất"}
            </button>
            <button onClick={() => setOpen(true)} className="button-secondary">
              <Plus size={17} /> Nhập chủ đề
            </button>
          </div>
        }
      />
      <section className="panel mb-7 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">Autopilot · NASA Earth Observatory</p>
            <h2 className="display mt-2 text-2xl font-bold">
              Khám phá mới thành truyện thiếu nhi
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Agent chọn bài khoa học/thiên nhiên trong 7 ngày gần đây, lưu
              nguồn và ngày xuất bản, viết kịch bản rồi xếp job dựng video. Mỗi
              bài chỉ được dùng một lần cho dự án. Video xem thử dùng ảnh NASA
              của bài và giọng đọc tiếng Việt khi bridge đang hoạt động. Hãy
              đối chiếu chi tiết khoa học với bài gốc trước khi xuất bản.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm font-bold">
            <input
              type="checkbox"
              checked={project.data?.autopilot_enabled ?? false}
              disabled={!project.data || toggleAutopilot.isPending}
              onChange={(event) => toggleAutopilot.mutate(event.target.checked)}
            />
            Chạy tự động 07:00 mỗi ngày
          </label>
        </div>
        {latestCandidate ? (
          <div className="mt-5 rounded-xl bg-[#f5f2ec] p-4">
            <p className="text-xs font-bold uppercase text-teal-700">
              Bài mới có thể dùng
            </p>
            <a
              href={latestCandidate.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-flex items-center gap-1 font-extrabold text-ink underline"
            >
              {latestCandidate.title} <ExternalLink size={14} />
            </a>
            <p className="mt-1 text-xs text-slate-500">
              NASA ·{" "}
              {new Date(latestCandidate.published_at).toLocaleString("vi-VN")}
            </p>
            <p className="mt-2 line-clamp-4 text-sm text-slate-600">
              {latestCandidate.summary}
            </p>
          </div>
        ) : preview.isLoading ? (
          <p className="mt-5 text-sm text-slate-500">
            Đang kiểm tra nguồn NASA…
          </p>
        ) : (
          <p className="mt-5 text-sm text-slate-500">
            {preview.error?.message ??
              "Hiện chưa có bài phù hợp và chưa được sử dụng."}
          </p>
        )}
        {[runAutopilot.error, toggleAutopilot.error, retrySource.error].map(
          (error, index) =>
            error && (
              <p key={index} role="alert" className="mt-3 text-sm text-red-700">
                {error.message}
              </p>
            ),
        )}
      </section>
      {sources.data?.length ? (
        <section className="mb-7">
          <h2 className="mb-3 text-lg font-extrabold">Truyện từ nguồn mới</h2>
          <div className="panel divide-y divide-[#ece8df]">
            {sources.data.map((source) => (
              <div
                key={source.id}
                className="flex flex-wrap items-center gap-4 p-4"
              >
                <div className="min-w-0 flex-1">
                  <a
                    href={source.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-bold underline"
                  >
                    {source.title}
                  </a>
                  <p className="mt-1 text-xs text-slate-500">
                    NASA ·{" "}
                    {new Date(source.published_at).toLocaleString("vi-VN")} ·{" "}
                    {source.model_snapshot.story_model}
                    {" · "}
                    {source.status}
                    {source.job_status ? ` · job ${source.job_status}` : ""}
                  </p>
                  {source.error_message && (
                    <p className="mt-2 text-xs text-red-700">
                      {source.error_message}
                    </p>
                  )}
                </div>
                {source.job_id ? (
                  <Link
                    className="button-secondary"
                    href={`/jobs/${source.job_id}`}
                  >
                    Xem video/job
                  </Link>
                ) : source.status === "failed" ? (
                  <button
                    className="button-secondary"
                    onClick={() => retrySource.mutate(source.id)}
                    disabled={retrySource.isPending}
                  >
                    <RotateCcw size={15} /> Thử lại
                  </button>
                ) : (
                  <span className="text-xs font-bold text-slate-500">
                    Đang viết truyện…
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      ) : null}
      <h2 className="mb-3 text-lg font-extrabold">Các tập của dự án</h2>
      {episodes.data?.length ? (
        <div className="panel divide-y divide-[#ece8df] overflow-hidden">
          {episodes.data.map((episode) => (
            <Link
              href={`/projects/${id}/episodes/${episode.id}/storyboard`}
              key={episode.id}
              className="flex items-center gap-4 p-5 hover:bg-white"
            >
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-teal-500/10 text-teal-600">
                <Film size={20} />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-extrabold">{episode.title}</h3>
                <p className="mt-1 text-xs text-slate-400">
                  {episode.aspect_ratio} ·{" "}
                  {Math.round(episode.duration_goal_ms / 1000)} giây · rev{" "}
                  {episode.revision}
                </p>
              </div>
              <StatusBadge status={episode.status} />
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="Chưa có tập truyện"
          message="Bấm Lấy tin mới & sản xuất để agent tự làm tập đầu tiên."
        />
      )}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/45 p-4"
        >
          <form onSubmit={submit} className="panel w-full max-w-lg p-6">
            <p className="eyebrow">Topic to storyboard</p>
            <h2 className="display mt-2 text-3xl font-bold">Tập truyện mới</h2>
            <div className="mt-6 grid gap-5">
              <label className="field-label">
                Chủ đề
                <textarea
                  name="topic"
                  className="field min-h-28 resize-none"
                  required
                  autoFocus
                  placeholder="Mimi học cách chia sẻ chiếc ô trong ngày mưa"
                />
              </label>
              <label className="field-label">
                Chế độ
                <select className="field" name="mode" defaultValue="automation">
                  <option value="automation">
                    Automation — quality gate tự động
                  </option>
                  <option value="studio">Studio — duyệt thủ công</option>
                </select>
              </label>
            </div>
            {create.error && (
              <p role="alert" className="mt-3 text-sm font-bold text-red-600">
                {create.error.message}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="button-secondary"
              >
                Hủy
              </button>
              <button disabled={create.isPending} className="button-primary">
                <Sparkles size={16} />
                {create.isPending ? "Đang viết truyện…" : "Tạo storyboard"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
