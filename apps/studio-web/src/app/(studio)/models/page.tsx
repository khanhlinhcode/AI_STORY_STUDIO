"use client";

import { Cpu, HardDrive, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { PageHeading } from "@/components/page-heading";
import { apiFetch } from "@/lib/api-client";

interface Capability {
  backend_id: string;
  available: boolean;
  task_types: string[];
  model_ids: string[];
  supported_formats: string[];
  unavailable_reason?: string;
  license_flags: string[];
}

interface Runtime {
  story_backend: string;
  story_model: string;
  story_ready: boolean;
  media_backend: string;
  image_backend: string;
  voice_backend: string;
  voice_ready: boolean;
  lora_name: string | null;
  lora_trained_here: boolean;
}

export default function ModelsPage() {
  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: () => apiFetch<Capability[]>("/models/capabilities"),
    refetchInterval: 15000,
  });
  const runtime = useQuery({
    queryKey: ["model-runtime"],
    queryFn: () => apiFetch<Runtime>("/models/runtime"),
    refetchInterval: 15000,
  });
  return (
    <>
      <PageHeading
        eyebrow="Model hub"
        title="Model đang chạy"
        description="Trạng thái thực tế của model viết truyện, tạo ảnh, giọng đọc và LoRA."
      />
      {runtime.data && (
        <section className="panel mb-7 grid gap-4 p-6 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {
              label: "Viết truyện",
              value:
                runtime.data.story_backend === "ollama"
                  ? runtime.data.story_model
                  : "Fixture",
              detail: runtime.data.story_ready
                ? "Sẵn sàng"
                : "Model chưa tải hoặc Ollama chưa kết nối",
            },
            {
              label: "Ảnh",
              value: runtime.data.image_backend,
              detail:
                runtime.data.media_backend === "fake"
                  ? "Ảnh NASA cho Autopilot; ảnh mẫu cho chủ đề tự nhập"
                  : "Cần kiểm tra backend",
            },
            {
              label: "Giọng đọc",
              value: runtime.data.voice_backend,
              detail:
                runtime.data.voice_backend === "fake"
                  ? "Chỉ âm thanh mẫu"
                  : runtime.data.voice_ready
                    ? "Giọng tiếng Việt đã kết nối"
                    : "Bridge giọng đọc chưa kết nối",
            },
            {
              label: "Character LoRA",
              value: runtime.data.lora_name ?? "Chưa có",
              detail: runtime.data.lora_trained_here
                ? "Đã huấn luyện tại Studio"
                : "Chưa huấn luyện/kiểm định",
            },
          ].map((item) => (
            <div key={item.label} className="rounded-xl bg-[#f5f2ec] p-4">
              <p className="text-xs font-bold uppercase text-slate-500">
                {item.label}
              </p>
              <p className="mt-2 break-words font-extrabold">{item.value}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {item.detail}
              </p>
            </div>
          ))}
        </section>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        {capabilities.data?.map((item) => (
          <article key={item.backend_id} className="panel p-6">
            <div className="flex items-start gap-4">
              <span
                className={`grid h-12 w-12 place-items-center rounded-2xl ${item.available ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"}`}
              >
                <Cpu size={21} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="font-extrabold uppercase">
                    {item.backend_id}
                  </h2>
                  <span
                    className={`flex items-center gap-1 text-xs font-bold ${item.available ? "text-emerald-600" : "text-slate-400"}`}
                  >
                    {item.available ? (
                      <Wifi size={13} />
                    ) : (
                      <WifiOff size={13} />
                    )}
                    {item.available ? "Kết nối được" : "Không khả dụng"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {item.task_types.join(" · ")}
                </p>
              </div>
            </div>
            <div className="mt-5 grid gap-3 rounded-xl bg-[#f5f2ec] p-4 text-sm">
              <div className="flex gap-2">
                <HardDrive size={16} className="shrink-0 text-slate-400" />
                <span>
                  {item.model_ids.length
                    ? item.model_ids.join(", ")
                    : "Chưa phát hiện model"}
                </span>
              </div>
              <div className="flex gap-2">
                <ShieldCheck size={16} className="shrink-0 text-slate-400" />
                <span>
                  {item.license_flags.join(", ") || "Không có cờ giấy phép"}
                </span>
              </div>
              {item.unavailable_reason && (
                <p className="text-xs leading-5 text-slate-500">
                  {item.unavailable_reason}
                </p>
              )}
            </div>
          </article>
        )) ??
          [1, 2].map((key) => (
            <div key={key} className="panel h-48 animate-pulse" />
          ))}
      </div>
    </>
  );
}
