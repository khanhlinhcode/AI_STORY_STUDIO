export type Status = "draft" | "queued" | "running" | "completed" | "failed" | "cancelled" | "pending" | "approved";

export interface Project {
  id: string;
  workspace_id: string;
  title: string;
  locale: string;
  audience: string;
  style_profile: Record<string, unknown>;
  status: string;
  version: number;
  autopilot_enabled: boolean;
}

export interface Episode {
  id: string;
  project_id: string;
  title: string;
  topic: string;
  duration_goal_ms: number;
  aspect_ratio: string;
  execution_mode: "automation" | "studio";
  status: string;
  revision: number;
}

export interface Scene {
  id: string;
  episode_id: string;
  order_index: number;
  synopsis: string;
  duration_ms: number;
  current_revision_id: string | null;
}

export interface SceneRevision {
  id: string;
  scene_id: string;
  prompt: string;
  image_desc: string;
  narration: string;
  camera: Record<string, unknown>;
  approval_state: string;
  seed: number;
}

export interface SceneImage {
  asset_id: string;
  scene_revision_id: string;
  seed: number;
  approved: boolean;
  url: string;
}

export interface JobStep {
  id: string;
  job_id: string;
  scene_revision_id: string | null;
  kind: string;
  attempts: number;
  max_attempts: number;
  status: Status;
  error_code: string | null;
}

export interface Job {
  id: string;
  workspace_id: string;
  episode_id: string;
  status: Status;
  priority: number;
  execution_mode: string;
  job_kind: string;
  error_code: string | null;
  error_message: string | null;
  snapshot_revision: number;
  steps?: JobStep[];
}

export interface JobArtifacts {
  manifest: {
    videos: Record<string, string>;
    srt: string;
    thumbnail: string;
    fixture_only: boolean;
    source_scene_revision_ids: string[];
  };
  qc: { blocking: boolean; blocking_issues: string[]; technical_checks: string[] } | null;
}

export interface Asset {
  id: string;
  workspace_id: string;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  rights_declaration: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
}

