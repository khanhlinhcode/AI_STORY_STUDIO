"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileImage, ShieldCheck, UploadCloud } from "lucide-react";
import Image from "next/image";
import { FormEvent, useState } from "react";
import { PageHeading } from "@/components/page-heading";
import { apiFetch } from "@/lib/api-client";
import type { Asset } from "@/lib/types";

const pageSize = 24;

export default function AssetsPage() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [mime, setMime] = useState("");
  const [offset, setOffset] = useState(0);
  const assets = useQuery({
    queryKey: ["assets", mime, offset],
    queryFn: () =>
      apiFetch<Asset[]>(
        `/assets?limit=${pageSize}&offset=${offset}${mime ? `&mime_type=${encodeURIComponent(mime)}` : ""}`,
      ),
  });

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    setUploading(true);
    setMessage("");
    const form = new FormData(formElement);
    form.set(
      "rights",
      JSON.stringify({
        source: form.get("source"),
        commercial_use: form.get("commercial") === "on",
      }),
    );
    try {
      const response = await fetch("/api/backend/assets/upload", {
        method: "POST",
        body: form,
      });
      const payload = await response.json();
      if (!response.ok)
        throw new Error(
          payload.error?.message ?? payload.detail ?? "Tải lên thất bại",
        );
      setMessage(`Đã lưu asset ${payload.sha256.slice(0, 12)}…`);
      setOffset(0);
      await queryClient.invalidateQueries({ queryKey: ["assets"] });
      formElement.reset();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Tải lên thất bại");
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="Asset registry"
        title="Tài nguyên"
        description="Media được nhận dạng nội dung bằng SHA-256, kiểm tra loại file và gắn khai báo quyền trước khi đi vào pipeline."
      />
      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <section className="panel min-h-80 p-5 sm:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-extrabold">Kho tài nguyên</h2>
            <select
              className="field max-w-52 text-sm"
              value={mime}
              onChange={(event) => {
                setMime(event.target.value);
                setOffset(0);
              }}
              aria-label="Lọc loại tài nguyên"
            >
              <option value="">Tất cả loại</option>
              <option value="image/png">Ảnh PNG</option>
              <option value="image/jpeg">Ảnh JPEG</option>
              <option value="audio/wav">Âm thanh WAV</option>
              <option value="video/mp4">Video MP4</option>
              <option value="text/plain">Phụ đề / văn bản</option>
            </select>
          </div>
          {assets.isLoading && (
            <p className="mt-8 text-sm text-slate-500">Đang tải tài nguyên…</p>
          )}
          {assets.error && (
            <p role="alert" className="mt-8 text-sm text-red-700">
              {assets.error.message}
            </p>
          )}
          {assets.data?.length === 0 && (
            <div className="grid min-h-60 place-items-center text-center">
              <div>
                <FileImage className="mx-auto text-teal-600" size={34} />
                <p className="mt-3 font-bold">
                  Chưa có tài nguyên trong mục này
                </p>
              </div>
            </div>
          )}
          {assets.data && assets.data.length > 0 && (
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {assets.data.map((asset) => (
                <a
                  key={asset.id}
                  href={`/api/backend/assets/${asset.id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="group overflow-hidden rounded-xl border border-[#e8e4dc] bg-white hover:border-teal-500"
                >
                  <div className="relative grid aspect-video place-items-center bg-[#efede7] text-slate-400">
                    {asset.mime_type.startsWith("image/") ? (
                      <Image
                        src={`/api/backend/assets/${asset.id}/download`}
                        alt={`Asset ${asset.sha256.slice(0, 12)}`}
                        fill
                        unoptimized
                        sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
                        className="object-cover"
                      />
                    ) : (
                      <FileImage size={28} />
                    )}
                  </div>
                  <div className="p-3">
                    <p className="truncate text-sm font-bold">
                      {asset.sha256.slice(0, 16)}…
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {asset.mime_type} ·{" "}
                      {(asset.size_bytes / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <p className="mt-1 truncate text-xs text-slate-400">
                      {String(
                        asset.rights_declaration.source ??
                          asset.rights_declaration.kind ??
                          "Không rõ nguồn",
                      )}
                    </p>
                  </div>
                </a>
              ))}
            </div>
          )}
          <div className="mt-6 flex items-center justify-between gap-3 text-sm">
            <button
              className="button-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - pageSize))}
            >
              Trang trước
            </button>
            <span>Trang {Math.floor(offset / pageSize) + 1}</span>
            <button
              className="button-secondary"
              disabled={!assets.data || assets.data.length < pageSize}
              onClick={() => setOffset(offset + pageSize)}
            >
              Trang sau
            </button>
          </div>
        </section>
        <form onSubmit={upload} className="panel grid content-start gap-5 p-5">
          <div>
            <p className="eyebrow">Secure ingest</p>
            <h2 className="display mt-2 text-2xl font-bold">Tải asset lên</h2>
          </div>
          <label className="field-label">
            File
            <input
              name="file"
              type="file"
              accept="image/png,image/jpeg,audio/wav,video/mp4"
              required
              className="field text-sm"
            />
          </label>
          <label className="field-label">
            Nguồn/quyền sở hữu
            <input
              name="source"
              className="field"
              placeholder="Tác phẩm gốc của tôi"
              required
            />
          </label>
          <label className="flex items-center gap-2 text-sm font-bold">
            <input type="checkbox" name="commercial" />
            <ShieldCheck size={16} className="text-teal-600" />
            Được phép sử dụng thương mại
          </label>
          <button className="button-primary" disabled={uploading}>
            <UploadCloud size={17} />
            {uploading ? "Đang tải lên…" : "Tải lên an toàn"}
          </button>
          {message && (
            <p
              role="status"
              className="rounded-xl bg-slate-100 p-3 text-sm font-bold"
            >
              {message}
            </p>
          )}
        </form>
      </div>
    </>
  );
}
