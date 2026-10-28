"use client";

import {
  closestCenter,
  DndContext,
  DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowLeft,
  Bot,
  ChevronLeft,
  ChevronRight,
  Film,
  GitCompareArrows,
  LockKeyhole,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorState } from "@/components/error-state";
import { SceneCard } from "@/components/scene-card";
import { StatusBadge } from "@/components/status-badge";
import { apiFetch } from "@/lib/api-client";
import {
  useEpisodeScenes,
  useSceneImages,
  useSceneRevisions,
} from "@/lib/queries";
import { useStudioStore } from "@/lib/studio-store";
import type { Episode, Job, Scene } from "@/lib/types";

function SortableScene({
  scene,
  selected,
  onSelect,
}: {
  scene: Scene;
  selected: boolean;
  onSelect: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: scene.id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "opacity-60" : ""}
      {...attributes}
      {...listeners}
    >
      <SceneCard scene={scene} selected={selected} onSelect={onSelect} />
    </div>
  );
}

export default function StoryboardPage() {
  const { id, epId } = useParams<{ id: string; epId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const episode = useQuery({
    queryKey: ["episode", epId],
    queryFn: () => apiFetch<Episode>(`/episodes/${epId}`),
  });
  const scenesQuery = useEpisodeScenes(epId);
  const [sceneOrder, setSceneOrder] = useState<string[]>([]);
  const { selectedSceneId, setSelectedScene, compareMode, toggleCompare } =
    useStudioStore();
  const scenes = useMemo(() => {
    const source = scenesQuery.data ?? [];
    if (!sceneOrder.length) return source;
    const position = new Map(
      sceneOrder.map((sceneId, index) => [sceneId, index]),
    );
    return [...source].sort(
      (a, b) =>
        (position.get(a.id) ?? a.order_index) -
        (position.get(b.id) ?? b.order_index),
    );
  }, [scenesQuery.data, sceneOrder]);
  const selectedIndex = Math.max(
    0,
    scenes.findIndex((scene) => scene.id === selectedSceneId),
  );
  const selected = scenes[selectedIndex];
  const revisions = useSceneRevisions(selected?.id);
  const images = useSceneImages(selected?.id);
  const [imagePromptDraft, setImagePromptDraft] = useState({
    sceneId: "",
    value: "",
  });
  const imagePrompt =
    imagePromptDraft.sceneId === selected?.id ? imagePromptDraft.value : "";
  const [variantJob, setVariantJob] = useState({ sceneId: "", jobId: "" });
  const variantJobId =
    variantJob.sceneId === selected?.id ? variantJob.jobId : "";
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const reorder = useMutation({
    mutationFn: (ids: string[]) =>
      apiFetch(`/episodes/${epId}/scenes/order`, {
        method: "PUT",
        body: JSON.stringify({ scene_ids: ids }),
      }),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["episode", epId, "scenes"] }),
  });
  function dragEnd(event: DragEndEvent) {
    if (!event.over || event.active.id === event.over.id) return;
    const oldIndex = scenes.findIndex((s) => s.id === event.active.id);
    const newIndex = scenes.findIndex((s) => s.id === event.over?.id);
    const ordered = arrayMove(scenes, oldIndex, newIndex).map(
      (scene, index) => ({ ...scene, order_index: index }),
    );
    setSceneOrder(ordered.map((scene) => scene.id));
    reorder.mutate(ordered.map((scene) => scene.id));
  }
  const start = useMutation({
    mutationFn: () =>
      apiFetch<Job>(`/episodes/${epId}/production/start`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: (job) => router.push(`/jobs/${job.id}`),
  });
  const currentRevision = revisions.data?.find(
    (revision) => revision.id === selected?.current_revision_id,
  );
  const candidateRevision = revisions.data?.find(
    (revision) => revision.id !== selected?.current_revision_id,
  );
  const regenerate = useMutation({
    mutationFn: () =>
      apiFetch<{ job_id: string }>(
        `/scenes/${selected?.id}/generate-image/regenerate`,
        {
          method: "POST",
          body: JSON.stringify({ prompt: imagePrompt.trim() || null }),
        },
      ),
    onSuccess: async (result) => {
      setVariantJob({ sceneId: selected?.id ?? "", jobId: result.job_id });
      setImagePromptDraft({ sceneId: selected?.id ?? "", value: "" });
      await queryClient.invalidateQueries({
        queryKey: ["scene", selected?.id],
      });
    },
  });
  const approve = useMutation({
    mutationFn: (revisionId: string) =>
      apiFetch(`/scenes/${selected?.id}/revisions/${revisionId}/approve`, {
        method: "POST",
        body: "{}",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["scene", selected?.id] }),
        queryClient.invalidateQueries({
          queryKey: ["episode", epId, "scenes"],
        }),
      ]);
    },
  });
  const imageA = images.data?.find(
    (item) => item.scene_revision_id === selected?.current_revision_id,
  );
  const imageB = images.data?.find(
    (item) => item.scene_revision_id === candidateRevision?.id,
  );
  const backdrop = useMemo(
    () =>
      selected
        ? `linear-gradient(145deg, hsl(${(selected.order_index * 47 + 160) % 360} 48% 30%), hsl(${(selected.order_index * 53 + 205) % 360} 55% 68%))`
        : "#e5e7eb",
    [selected],
  );
  if (scenesQuery.error)
    return (
      <ErrorState
        message={scenesQuery.error.message}
        retry={() => scenesQuery.refetch()}
      />
    );
  return (
    <div className="-m-4 sm:-m-7 xl:-m-9">
      <header className="flex min-h-20 flex-wrap items-center gap-3 border-b border-[#e3ded4] bg-panel px-4 py-3 sm:px-6">
        <Link
          href={`/projects/${id}`}
          className="rounded-lg p-2 hover:bg-slate-100"
          aria-label="Quay lại dự án"
        >
          <ArrowLeft size={19} />
        </Link>
        <div className="min-w-0">
          <p className="text-xs font-bold text-slate-400">
            {episode.data?.execution_mode === "automation"
              ? "AUTOMATION"
              : "STUDIO"}{" "}
            / STORYBOARD
          </p>
          <h1 className="truncate font-extrabold">
            {episode.data?.title ?? "Đang tải…"}
          </h1>
        </div>
        <StatusBadge status={episode.data?.status ?? "draft"} />
        <div className="ml-auto flex gap-2">
          <button onClick={toggleCompare} className="button-secondary">
            <GitCompareArrows size={16} />
            <span className="hidden sm:inline">So sánh A/B</span>
          </button>
          <button
            onClick={() => start.mutate()}
            disabled={start.isPending || !scenes.length}
            className="button-primary"
          >
            <Film size={16} />
            {start.isPending ? "Đang xếp hàng…" : "Sản xuất"}
          </button>
        </div>
      </header>
      <div className="grid min-h-[calc(100vh-9rem)] xl:grid-cols-[292px_minmax(0,1fr)_330px]">
        <aside className="border-b border-[#e3ded4] bg-[#efede7] p-3 xl:border-b-0 xl:border-r">
          <div className="mb-3 flex items-center justify-between px-2">
            <p className="text-xs font-black uppercase tracking-wider text-slate-500">
              Các cảnh · {scenes.length}
            </p>
            <span className="text-[10px] font-bold text-slate-400">
              KÉO ĐỂ ĐỔI THỨ TỰ
            </span>
          </div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={dragEnd}
          >
            <SortableContext
              items={scenes.map((scene) => scene.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="grid max-h-[calc(100vh-11rem)] gap-2 overflow-y-auto pr-1">
                {scenes.map((scene) => (
                  <SortableScene
                    key={scene.id}
                    scene={scene}
                    selected={selected?.id === scene.id}
                    onSelect={() => setSelectedScene(scene.id)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </aside>
        <section className="flex min-h-[560px] flex-col bg-[#e8e5de] p-4 sm:p-7">
          <div
            className={`grid flex-1 gap-4 ${compareMode ? "md:grid-cols-2" : ""}`}
          >
            {["Version A", ...(compareMode ? ["Version B"] : [])].map(
              (version, index) => (
                <figure
                  key={version}
                  className="relative min-h-[420px] overflow-hidden rounded-2xl shadow-2xl"
                  style={{ background: backdrop }}
                >
                  <div
                    className="absolute inset-0 opacity-30"
                    style={{
                      backgroundImage:
                        "radial-gradient(circle at 25% 20%, white 0 2px, transparent 3px), linear-gradient(120deg, transparent 45%, rgba(255,255,255,.3) 46%, transparent 47%)",
                      backgroundSize: "28px 28px, auto",
                    }}
                  />
                  {(index === 0 ? imageA : imageB) && (
                    <Image
                      src={(index === 0 ? imageA : imageB)?.url ?? ""}
                      alt={`Ảnh ${version} của cảnh ${selectedIndex + 1}`}
                      fill
                      unoptimized
                      sizes={
                        compareMode ? "(min-width: 768px) 50vw, 100vw" : "100vw"
                      }
                      className="absolute inset-0 h-full w-full object-cover"
                    />
                  )}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-6 pt-20 text-white">
                    <p className="text-xs font-black uppercase tracking-widest text-white/60">
                      {version}
                    </p>
                    <p className="display mt-2 text-2xl font-bold">
                      {index === 0
                        ? selected?.synopsis
                        : (candidateRevision?.image_desc ?? "Chưa có biến thể")}
                    </p>
                  </div>
                  <span className="absolute right-4 top-4 rounded-full bg-black/25 px-3 py-1.5 text-xs font-bold text-white backdrop-blur">
                    {(index === 0 ? imageA : imageB)
                      ? "Ảnh đã render"
                      : "Chưa có ảnh"}
                  </span>
                </figure>
              ),
            )}
          </div>
          <div className="mx-auto mt-5 flex items-center gap-2 rounded-full border border-white/60 bg-white/80 p-2 shadow-lg backdrop-blur">
            <button
              disabled={selectedIndex <= 0}
              onClick={() => setSelectedScene(scenes[selectedIndex - 1].id)}
              className="rounded-full p-2 hover:bg-slate-100 disabled:opacity-30"
              aria-label="Cảnh trước"
            >
              <ChevronLeft />
            </button>
            <span className="px-3 text-xs font-bold text-slate-600">
              Ảnh cảnh {selectedIndex + 1}/{scenes.length}
            </span>
            <button
              disabled={selectedIndex >= scenes.length - 1}
              onClick={() => setSelectedScene(scenes[selectedIndex + 1].id)}
              className="rounded-full p-2 hover:bg-slate-100 disabled:opacity-30"
              aria-label="Cảnh sau"
            >
              <ChevronRight />
            </button>
          </div>
        </section>
        <aside className="border-t border-[#e3ded4] bg-panel p-5 xl:border-l xl:border-t-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="eyebrow">Inspector</p>
              <h2 className="display mt-1 text-2xl font-bold">
                Cảnh {selectedIndex + 1}
              </h2>
            </div>
            {episode.data?.execution_mode === "automation" ? (
              <span className="flex items-center gap-1 rounded-full bg-teal-500/10 px-2.5 py-1 text-xs font-bold text-teal-700">
                <Bot size={13} />
                Auto QC
              </span>
            ) : (
              <StatusBadge
                status={currentRevision?.approval_state ?? "pending"}
              />
            )}
          </div>
          <div className="mt-6 grid gap-5">
            <div className="rounded-xl border border-[#e5e1d8] p-3">
              <div className="flex items-center gap-2 text-xs font-extrabold text-slate-500">
                <LockKeyhole size={14} />
                CHARACTER LOCK
              </div>
              <p className="mt-2 text-sm font-bold">
                Nhân vật theo hồ sơ dự án
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-400">
                Ngoại hình và trang phục được giữ cố định.
              </p>
            </div>
            <label className="field-label">
              Image prompt
              <textarea
                className="field min-h-32 resize-none text-sm leading-6"
                onChange={(event) =>
                  setImagePromptDraft({
                    sceneId: selected?.id ?? "",
                    value: event.target.value,
                  })
                }
                placeholder={
                  currentRevision?.prompt ?? "Nhập prompt cho biến thể mới"
                }
                value={imagePrompt}
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="field-label">
                Seed
                <input
                  className="field"
                  value={currentRevision?.seed ?? ""}
                  readOnly
                />
              </label>
              <label className="field-label">
                Camera
                <input
                  className="field"
                  value={String(currentRevision?.camera?.movement ?? "static")}
                  readOnly
                />
              </label>
            </div>
            <div>
              <p className="field-label">Narration</p>
              <p className="mt-2 rounded-xl bg-[#f5f2ec] p-3 text-sm leading-6">
                {currentRevision?.narration ?? selected?.synopsis}
              </p>
            </div>
            <div className="rounded-xl bg-ink p-4 text-white">
              <div className="flex items-center gap-2 text-sm font-bold">
                <Sparkles size={16} className="text-teal-500" />
                Chi phí ước tính
              </div>
              <div className="mt-3 flex justify-between text-xs text-slate-400">
                <span>Fake / local</span>
                <strong className="text-white">$0.00</strong>
              </div>
            </div>
            <button
              className="button-secondary w-full"
              disabled={!selected || regenerate.isPending}
              onClick={() => regenerate.mutate()}
            >
              <RefreshCw size={16} />
              {regenerate.isPending ? "Đang xếp hàng…" : "Tạo biến thể cảnh"}
            </button>
            {regenerate.error && (
              <p role="alert" className="text-sm text-red-700">
                {regenerate.error.message}
              </p>
            )}
            {variantJobId && (
              <Link
                href={`/jobs/${variantJobId}`}
                className="text-sm font-bold text-teal-700 underline"
              >
                Theo dõi job tạo ảnh
              </Link>
            )}
            {compareMode && candidateRevision && (
              <button
                className="button-primary w-full"
                disabled={!imageB || approve.isPending}
                onClick={() => approve.mutate(candidateRevision.id)}
              >
                {approve.isPending ? "Đang duyệt…" : "Chọn Version B"}
              </button>
            )}
            {approve.error && (
              <p role="alert" className="text-sm text-red-700">
                {approve.error.message}
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
