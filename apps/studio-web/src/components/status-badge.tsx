import { CheckCircle2, CircleDashed, CircleX, Clock3, LoaderCircle } from "lucide-react";

const views: Record<string, { label: string; className: string; icon: typeof Clock3 }> = {
  draft: { label: "Bản nháp", className: "bg-slate-100 text-slate-600", icon: CircleDashed },
  pending: { label: "Chờ duyệt", className: "bg-amber-50 text-amber-700", icon: Clock3 },
  queued: { label: "Trong hàng đợi", className: "bg-sky-50 text-sky-700", icon: Clock3 },
  running: { label: "Đang chạy", className: "bg-indigo-50 text-indigo-700", icon: LoaderCircle },
  completed: { label: "Hoàn tất", className: "bg-emerald-50 text-emerald-700", icon: CheckCircle2 },
  approved: { label: "Đã duyệt", className: "bg-emerald-50 text-emerald-700", icon: CheckCircle2 },
  failed: { label: "Thất bại", className: "bg-red-50 text-red-700", icon: CircleX },
  cancelled: { label: "Đã hủy", className: "bg-slate-100 text-slate-500", icon: CircleX },
};

export function StatusBadge({ status }: { status: string }) {
  const view = views[status] ?? views.draft; const Icon = view.icon;
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-extrabold ${view.className}`}><Icon size={13} className={status === "running" ? "animate-spin" : ""}/>{view.label}</span>;
}

