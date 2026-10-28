import { TriangleAlert } from "lucide-react";

export function ErrorState({ title = "Không tải được dữ liệu", message, retry }: { title?: string; message: string; retry?: () => void }) { return <div className="panel grid min-h-48 place-items-center p-7 text-center"><div><TriangleAlert className="mx-auto text-coral"/><h3 className="mt-3 font-extrabold">{title}</h3><p className="mt-2 text-sm text-slate-500">{message}</p>{retry && <button onClick={retry} className="button-secondary mt-4">Thử lại</button>}</div></div>; }

