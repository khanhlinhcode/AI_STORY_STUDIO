import { Sparkles } from "lucide-react";

export function EmptyState({ title, message, action }: { title: string; message: string; action?: React.ReactNode }) { return <div className="panel grid min-h-56 place-items-center p-8 text-center"><div><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-teal-500/10 text-teal-600"><Sparkles size={20}/></span><h3 className="display mt-4 text-2xl font-bold">{title}</h3><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">{message}</p>{action && <div className="mt-5">{action}</div>}</div></div>; }

