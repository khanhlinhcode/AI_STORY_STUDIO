"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Clock3,
  RotateCcw,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { JobProgressBar } from "@/components/job-progress-bar";
import { PageHeading } from "@/components/page-heading";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api-client";
import { useJobStatus } from "@/lib/queries";
import type { JobArtifacts, JobStep } from "@/lib/types";

const stepIcon = (status: string) =>
  status === "completed" ? (
    <Check size={15} />
  ) : status === "failed" ? (
    <X size={15} />
  ) : (
    <Clock3 size={15} />
  );

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const queryClient = useQueryClient();
  const job = useJobStatus(jobId);
  const artifacts = useQuery({
    queryKey: ["job", jobId, "artifacts"],
    queryFn: () => apiFetch<JobArtifacts>(`/jobs/${jobId}/artifacts`),
    enabled:
      job.data?.status === "completed" && job.data?.job_kind === "episode",
  });
  const retry = useMutation({
    mutationFn: (step: JobStep) =>
      apiFetch(`/jobs/${jobId}/retry-step/${step.id}`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["job", jobId] }),
  });
  const cancel = useMutation({
    mutationFn: () =>
      apiFetch(`/jobs/${jobId}/cancel`, { method: "POST", body: "{}" }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["job", jobId] }),
  });
  const steps = job.data?.steps ?? [];
  return (
    <>
      <Link
        href="/jobs"
        className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-slate-500"
      >
        <ArrowLeft size={16} />
        Job Center
      </Link>
      <PageHeading
        eyebrow="Production job"
        title={`Job ${jobId.slice(0, 8)}`}
        description="Mỗi bước có lease, retry budget và artifact riêng; trạng thái bền vững nằm trong PostgreSQL."
        action={job.data && <StatusBadge status={job.data.status} />}
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <section className="panel p-5 sm:p-7">
          <h2 className="text-lg font-extrabold">Step timeline</h2>
          <div className="mt-4">
            <JobProgressBar steps={steps} />
          </div>
          <ol className="mt-7 grid gap-3">
            {steps.map((step, index) => (
              <li
                key={step.id}
                className={`flex gap-4 rounded-xl border p-4 ${step.status === "failed" ? "border-red-200 bg-red-50" : "border-[#ebe7de] bg-white"}`}
              >
                <span
                  className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-black ${step.status === "completed" ? "bg-emerald-100 text-emerald-700" : step.status === "failed" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500"}`}
                >
                  {stepIcon(step.status)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-extrabold capitalize">
                      {index + 1}. {step.kind}
                    </p>
                    <StatusBadge status={step.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    Attempts {step.attempts}/{step.max_attempts}
                    {step.scene_revision_id
                      ? ` · Scene ${step.scene_revision_id.slice(0, 6)}`
                      : " · Episode scope"}
                  </p>
                  {step.error_code && (
                    <p className="mt-2 flex items-center gap-2 text-sm font-bold text-red-700">
                      <AlertTriangle size={15} />
                      {step.error_code}
                    </p>
                  )}
                </div>
                {step.status === "failed" && (
                  <button
                    onClick={() => retry.mutate(step)}
                    className="button-secondary"
                  >
                    <RotateCcw size={15} />
                    Retry
                  </button>
                )}
              </li>
            ))}
          </ol>
          {artifacts.data && (
            <section className="mt-8 border-t border-[#ebe7de] pt-7">
              <h2 className="text-lg font-extrabold">Preview đã render</h2>
              {artifacts.data.manifest.fixture_only && (
                <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                  Bản xem thử dùng ảnh và giọng mẫu; QC đang chặn xuất bản.
                </p>
              )}
              <video
                controls
                preload="metadata"
                poster={`/api/backend/assets/${artifacts.data.manifest.thumbnail}/download`}
                className="mt-4 aspect-video w-full rounded-xl bg-black"
                src={`/api/backend/assets/${artifacts.data.manifest.videos["16x9"]}/download`}
              />
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(artifacts.data.manifest.videos).map(
                  ([preset, assetId]) => (
                    <a
                      key={preset}
                      className="button-secondary"
                      href={`/api/backend/assets/${assetId}/download`}
                      download={`episode-${preset}.mp4`}
                    >
                      MP4 {preset}
                    </a>
                  ),
                )}
                <a
                  className="button-secondary"
                  href={`/api/backend/assets/${artifacts.data.manifest.srt}/download`}
                  download="captions.srt"
                >
                  SRT
                </a>
              </div>
              {artifacts.data.qc?.blocking && (
                <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-bold">QC cần xử lý trước khi xuất bản</p>
                  <ul className="mt-2 list-disc pl-5">
                    {artifacts.data.qc.blocking_issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}
        </section>
        <aside className="grid content-start gap-5">
          <div className="panel p-5">
            <p className="eyebrow">Snapshot</p>
            <dl className="mt-4 grid gap-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Mode</dt>
                <dd className="font-bold">{job.data?.execution_mode}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Episode rev</dt>
                <dd className="font-bold">{job.data?.snapshot_revision}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Priority</dt>
                <dd className="font-bold">{job.data?.priority}</dd>
              </div>
            </dl>
          </div>
          {job.data &&
            !["completed", "failed", "cancelled"].includes(job.data.status) && (
              <button
                onClick={() => cancel.mutate()}
                className="button-secondary !border-red-200 !text-red-700"
              >
                <X size={16} />
                Hủy job an toàn
              </button>
            )}
          {job.data?.status === "completed" && (
            <Link
              href={`/episodes/${job.data.episode_id}/export`}
              className="button-primary"
            >
              Mở Quality & Export
            </Link>
          )}
        </aside>
      </div>
    </>
  );
}
