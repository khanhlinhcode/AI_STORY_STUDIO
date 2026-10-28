import { GripVertical, Timer } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import type { Scene } from "@/lib/types";

export function SceneCard({ scene, selected, onSelect }: { scene: Scene; selected?: boolean; onSelect?: () => void }) {
  return <button onClick={onSelect} aria-pressed={selected} className={`group flex w-full gap-3 rounded-xl border p-3 text-left transition ${selected ? "border-teal-500 bg-teal-500/5 shadow-sm" : "border-transparent bg-white hover:border-slate-200"}`}><GripVertical className="mt-1 shrink-0 text-slate-300" size={16}/><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-black uppercase tracking-wider text-slate-400">Cảnh {scene.order_index + 1}</span><StatusBadge status="approved"/></div><p className="mt-2 line-clamp-2 text-sm font-bold leading-5">{scene.synopsis}</p><span className="mt-2 flex items-center gap-1 text-xs font-semibold text-slate-400"><Timer size={13}/>{(scene.duration_ms / 1000).toFixed(1)} giây</span></div></button>;
}

