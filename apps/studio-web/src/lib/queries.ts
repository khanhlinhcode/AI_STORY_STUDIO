"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { Job, Project, Scene, SceneImage, SceneRevision } from "@/lib/types";

export const useProjects = () => useQuery({ queryKey: ["projects"], queryFn: () => apiFetch<Project[]>("/projects") });

export const useEpisodeScenes = (episodeId: string) => useQuery({
  queryKey: ["episode", episodeId, "scenes"],
  queryFn: () => apiFetch<Scene[]>(`/episodes/${episodeId}/scenes`),
});

export const useSceneRevisions = (sceneId?: string) => useQuery({
  queryKey: ["scene", sceneId, "revisions"],
  queryFn: () => apiFetch<SceneRevision[]>(`/scenes/${sceneId}/revisions`),
  enabled: Boolean(sceneId),
});

export const useSceneImages = (sceneId?: string) => useQuery({
  queryKey: ["scene", sceneId, "images"],
  queryFn: () => apiFetch<SceneImage[]>(`/scenes/${sceneId}/images`),
  enabled: Boolean(sceneId),
  refetchInterval: 4000,
});

export const useJobStatus = (jobId: string) => useQuery({
  queryKey: ["job", jobId],
  queryFn: () => apiFetch<Job>(`/jobs/${jobId}`),
  refetchInterval: (query) => !query.state.data || !["completed", "failed", "cancelled"].includes(query.state.data.status) ? 2000 : false,
});

