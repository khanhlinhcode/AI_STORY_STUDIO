"use client";

import { Download, ShieldAlert, Youtube } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeading } from "@/components/page-heading";
import { apiFetch } from "@/lib/api-client";
import type { Episode, Job, JobArtifacts } from "@/lib/types";

interface ExportRecord {
  id: string;
  episode_id: string;
  episode_revision: number;
  status: string;
  manifest: { presets: string[]; bundle_asset_id: string };
}

interface PublishPackage {
  youtube: { title: string; made_for_kids: boolean; tags: string[] };
  tiktok: { caption: string };
  checklist: string[];
}

interface ScriptRevision {
  id: string;
  is_approved: boolean;
}

interface ReviewTask {
  id: string;
  reviewer_id: string;
  episode_revision: number;
  status: string;
}

export default function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [reviewNotes, setReviewNotes] = useState("");
  const episode = useQuery({
    queryKey: ["episode", id],
    queryFn: () => apiFetch<Episode>(`/episodes/${id}`),
  });
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiFetch<Job[]>("/jobs"),
  });
  const latestJob = jobs.data?.find(
    (job) => job.episode_id === id && job.job_kind === "episode",
  );
  const artifacts = useQuery({
    queryKey: ["job", latestJob?.id, "artifacts"],
    queryFn: () => apiFetch<JobArtifacts>(`/jobs/${latestJob!.id}/artifacts`),
    enabled: latestJob?.status === "completed",
  });
  const exports = useQuery({
    queryKey: ["episode", id, "exports"],
    queryFn: () => apiFetch<ExportRecord[]>(`/episodes/${id}/exports`),
  });
  const latestExport = exports.data?.[0];
  const studioMode = episode.data?.execution_mode === "studio";
  const me = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiFetch<{ id: string; display_name: string }>("/auth/me"),
    enabled: studioMode,
  });
  const scripts = useQuery({
    queryKey: ["episode", id, "scripts"],
    queryFn: () =>
      apiFetch<ScriptRevision[]>(`/episodes/${id}/script/revisions`),
    enabled: studioMode,
  });
  const reviews = useQuery({
    queryKey: ["episode", id, "reviews"],
    queryFn: () => apiFetch<ReviewTask[]>(`/episodes/${id}/reviews`),
    enabled: studioMode,
  });
  const latestReview = reviews.data?.find(
    (task) => task.episode_revision === episode.data?.revision,
  );
  const approveScript = useMutation({
    mutationFn: () =>
      apiFetch(`/script-revisions/${scripts.data![0].id}/approve`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["episode", id, "scripts"] }),
  });
  const assignReview = useMutation({
    mutationFn: () =>
      apiFetch(`/episodes/${id}/reviews`, {
        method: "POST",
        body: JSON.stringify({ reviewer_id: me.data!.id }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["episode", id, "reviews"] }),
  });
  const decideReview = useMutation({
    mutationFn: (verdict: "approved" | "rejected") =>
      apiFetch(`/reviews/${latestReview!.id}/decision`, {
        method: "POST",
        body: JSON.stringify({
          verdict,
          notes: reviewNotes,
          rubric_scores: {},
        }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["episode", id, "reviews"] }),
  });
  const publish = useQuery({
    queryKey: ["export", latestExport?.id, "publish"],
    queryFn: () =>
      apiFetch<PublishPackage>(`/exports/${latestExport!.id}/publish-package`),
    enabled: Boolean(latestExport),
  });
  const create = useMutation({
    mutationFn: () =>
      apiFetch<ExportRecord>(`/episodes/${id}/export`, {
        method: "POST",
        body: JSON.stringify({ presets: ["16:9", "9:16"] }),
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["episode", id, "exports"] }),
  });
  const blocking = artifacts.data?.qc?.blocking ?? true;
  const canExport =
    latestJob?.status === "completed" &&
    latestJob.snapshot_revision === episode.data?.revision &&
    !blocking &&
    (!studioMode ||
      (scripts.data?.[0]?.is_approved && latestReview?.status === "approved"));

  return (
    <>
      <PageHeading
        eyebrow="Quality & export"
        title={episode.data?.title ?? "Gói xuất bản"}
        description="Chỉ xuất bản khi job mới nhất qua QC và các bước duyệt nội dung đã hoàn tất."
        action={
          <button
            onClick={() => create.mutate()}
            disabled={!canExport || create.isPending}
            className="button-primary"
          >
            <Download size={17} />
            {create.isPending ? "Đang tạo ZIP…" : "Tạo gói export"}
          </button>
        }
      />
      {create.error && (
        <div
          role="alert"
          className="mb-6 flex gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800"
        >
          <ShieldAlert className="shrink-0" />
          <p>{create.error.message}</p>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="panel p-6">
          <h2 className="text-lg font-extrabold">Kết quả kiểm tra</h2>
          {!latestJob ? (
            <p className="mt-4 text-sm text-slate-600">
              Tập này chưa có job sản xuất.
            </p>
          ) : (
            <div className="mt-4 space-y-4 text-sm">
              <p>
                Job{" "}
                <Link
                  href={`/jobs/${latestJob.id}`}
                  className="font-bold text-teal-700 underline"
                >
                  {latestJob.id.slice(0, 8)}
                </Link>{" "}
                · {latestJob.status} · revision {latestJob.snapshot_revision}
              </p>
              {latestJob.status === "completed" && artifacts.isLoading && (
                <p>Đang tải báo cáo QC…</p>
              )}
              {artifacts.error && (
                <p role="alert" className="text-red-700">
                  {artifacts.error.message}
                </p>
              )}
              {artifacts.data?.qc && (
                <>
                  <p
                    className={
                      blocking
                        ? "font-bold text-amber-800"
                        : "font-bold text-emerald-700"
                    }
                  >
                    {blocking ? "QC đang chặn export" : "QC đã đạt"}
                  </p>
                  {artifacts.data.qc.blocking_issues.length > 0 && (
                    <ul className="list-disc space-y-1 pl-5 text-amber-900">
                      {artifacts.data.qc.blocking_issues.map((issue) => (
                        <li key={issue}>{issue}</li>
                      ))}
                    </ul>
                  )}
                  {artifacts.data.qc.technical_checks.length > 0 && (
                    <div>
                      <p className="font-bold">Kiểm tra kỹ thuật</p>
                      <ul className="mt-2 list-disc pl-5 text-slate-600">
                        {artifacts.data.qc.technical_checks.map((check) => (
                          <li key={check}>{check}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          {studioMode && (
            <div className="mt-7 border-t border-[#ebe7de] pt-6 text-sm">
              <h3 className="font-extrabold">Duyệt nội dung Studio</h3>
              <p className="mt-2 text-slate-600">
                Script mới nhất:{" "}
                {scripts.data?.[0]?.is_approved ? "đã duyệt" : "chưa duyệt"}.{" "}
                Review revision {episode.data?.revision}:{" "}
                {latestReview?.status ?? "chưa tạo"}.
              </p>
              {scripts.data?.[0] && !scripts.data[0].is_approved && (
                <button
                  className="button-secondary mt-4"
                  disabled={approveScript.isPending}
                  onClick={() => approveScript.mutate()}
                >
                  Duyệt script
                </button>
              )}
              {(!latestReview || latestReview.status === "rejected") && me.data && (
                <button
                  className="button-secondary mt-4"
                  disabled={assignReview.isPending}
                  onClick={() => assignReview.mutate()}
                >
                  Nhận nhiệm vụ review
                </button>
              )}
              {latestReview?.status === "pending" &&
                latestReview.reviewer_id === me.data?.id && (
                  <div className="mt-4 space-y-3">
                    <label className="field-label">
                      Ghi chú review
                      <textarea
                        className="field min-h-24"
                        value={reviewNotes}
                        onChange={(event) => setReviewNotes(event.target.value)}
                      />
                    </label>
                    <div className="flex gap-2">
                      <button
                        className="button-primary"
                        disabled={decideReview.isPending}
                        onClick={() => decideReview.mutate("approved")}
                      >
                        Duyệt nội dung
                      </button>
                      <button
                        className="button-secondary"
                        disabled={decideReview.isPending}
                        onClick={() => decideReview.mutate("rejected")}
                      >
                        Yêu cầu sửa
                      </button>
                    </div>
                  </div>
                )}
              {[
                approveScript.error,
                assignReview.error,
                decideReview.error,
              ].map(
                (error, index) =>
                  error && (
                    <p key={index} role="alert" className="mt-3 text-red-700">
                      {error.message}
                    </p>
                  ),
              )}
            </div>
          )}
        </section>
        <aside className="panel p-6">
          <Youtube className="text-red-600" />
          <h2 className="display mt-4 text-2xl font-bold">Publish package</h2>
          {latestExport ? (
            <>
              <p className="mt-3 text-sm text-slate-500">
                Gói {latestExport.id.slice(0, 8)} · revision{" "}
                {latestExport.episode_revision}
              </p>
              <a
                className="button-secondary mt-5 w-full"
                href={`/api/backend/exports/${latestExport.id}/download`}
                download={`story-${id}.zip`}
              >
                <Download size={16} /> Tải ZIP
              </a>
              {publish.data && (
                <div className="mt-5 space-y-3 text-sm text-slate-600">
                  <p>
                    <strong>YouTube:</strong> {publish.data.youtube.title}
                  </p>
                  <p>
                    <strong>Made for Kids:</strong>{" "}
                    {publish.data.youtube.made_for_kids ? "Có" : "Không"}
                  </p>
                  <p>
                    <strong>TikTok:</strong> {publish.data.tiktok.caption}
                  </p>
                  <ul className="list-disc pl-5">
                    {publish.data.checklist.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">
              Chưa có gói xuất bản. Video fixture chỉ có thể xem thử trong Job
              Center.
            </p>
          )}
        </aside>
      </div>
    </>
  );
}
