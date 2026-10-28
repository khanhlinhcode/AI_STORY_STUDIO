import type { JobStep } from "@/lib/types";

export function JobProgressBar({ steps }: { steps: JobStep[] }) {
  const complete = steps.filter((step) => step.status === "completed").length;
  const progress = steps.length ? Math.round((complete / steps.length) * 100) : 0;
  return <div aria-label={`Tiến độ ${progress}%`} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><div className="mb-2 flex justify-between text-xs font-bold text-slate-500"><span>{complete}/{steps.length} bước</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-teal-500 transition-all" style={{ width: `${progress}%` }}/></div></div>;
}

