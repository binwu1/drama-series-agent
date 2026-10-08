const BASE =
  import.meta.env.VITE_HERMES_API_BASE || "http://127.0.0.1:8000/api/series";

export type Conversation = {
  conversation_id: string;
  series_id: string;
  project_dir: string;
  title: string;
  updated_at?: string;
};

export type StatusPayload = {
  series_id?: string;
  stage?: string;
  next_episode?: number | string;
  s1_gate?: Record<string, unknown>;
  active_job_ids?: string[];
  enrich_jobs?: Array<{
    job_id?: string;
    job_kind?: string;
    status?: string;
    created_at?: string;
  }>;
  open_workbench?: boolean;
  status_label_zh?: string;
  series_bible?: {
    bible_ready?: boolean;
    missing?: string[];
    core_missing?: string[];
    docs?: Array<{
      file?: string;
      label?: string;
      ready?: boolean;
      path?: string;
    }>;
  };
  artifacts?: {
    literary?: {
      ok?: boolean;
      premise?: string;
      genre?: string;
      literary_accepted?: boolean;
      episodes?: Array<{
        episode_id?: string;
        status?: string;
        status_zh?: string;
        preview?: string;
        mtime?: string;
      }>;
    };
    cast?: {
      ok?: boolean;
      assets?: Array<{
        name?: string;
        role?: string;
        status?: string;
        status_zh?: string;
        has_draft?: boolean;
        has_final?: boolean;
      }>;
    };
  };
  s2?: {
    episode_id?: string;
    default_workflow?: string | null;
    aspect?: string;
    context_ir?: string;
    ready_for_s2?: boolean;
    jsonl_exists?: boolean;
    jsonl_path?: string | null;
    shot_count?: number | null;
    valid?: boolean | null;
    errors?: string[];
    episode_status?: string;
    resume_from_shot?: string | null;
  };
};

export type ChatMessage = {
  role: string;
  content: string;
  ts?: string;
  ui_hints?: { open_workbench?: boolean };
};

async function jsonOrThrow(r: Response) {
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

export async function listConversations(): Promise<Conversation[]> {
  return jsonOrThrow(await fetch(`${BASE}/conversations`));
}

export async function createConversation(
  title: string,
  premise?: string,
): Promise<Conversation> {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, premise }),
    }),
  );
}

export async function getConversation(
  id: string,
): Promise<Conversation & { status: StatusPayload }> {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${id}`));
}

export async function getMessages(id: string): Promise<ChatMessage[]> {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${id}/messages`));
}

export async function postMessage(
  id: string,
  content: string,
): Promise<{
  assistant_message: ChatMessage;
  status: StatusPayload;
  tool_trace?: unknown[];
}> {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }),
  );
}

export async function acceptLiterary(id: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/actions/accept_literary`, {
      method: "POST",
    }),
  );
}

export async function acceptCast(id: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/actions/accept_cast`, {
      method: "POST",
    }),
  );
}

export async function deferAudio(id: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/actions/defer_audio`, {
      method: "POST",
    }),
  );
}

export async function s2Build(id: string, episodeId?: string, force = false) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/s2/build`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId, force }),
    }),
  );
}

export async function s2Validate(id: string, episodeId?: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/s2/validate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId }),
    }),
  );
}

export async function s2Comfy(id: string, episodeId?: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${id}/s2/comfy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ episode_id: episodeId, run_in_background: true }),
    }),
  );
}

export function eventsUrl(id: string) {
  return `${BASE}/conversations/${id}/events`;
}

export type JobSnap = {
  job_id?: string;
  job_kind?: string;
  series_id?: string;
  episode_id?: string;
  status?: string;
  phase?: string;
  progress?: number;
  shot_id?: string;
  index?: number;
  total?: number;
  error?: string;
  master_path?: string;
  message?: string;
};

export type JobEventRow = {
  event_type?: string;
  job_kind?: string;
  job_id?: string;
  episode_id?: string;
  shot_id?: string;
  phase?: string;
  progress?: number;
  message?: string;
  error?: string;
  ts?: string;
};

export type EpisodeShotProgress = {
  shot_id: string;
  order?: number;
  duration_seconds?: number;
  has_video?: boolean;
  has_tail?: boolean;
  complete?: boolean;
  video_bytes?: number;
};

export type EpisodeProgress = {
  episode_id: string;
  jsonl_exists?: boolean;
  shot_total?: number;
  shot_done?: number;
  all_shots_complete?: boolean;
  master_ready?: boolean;
  master_bytes?: number;
  resume_from_shot?: string | null;
  continue_from_shot?: string | null;
  runtime_status?: string | null;
  progress_status?: string;
  workflow?: string | null;
  shots?: EpisodeShotProgress[];
};

export async function getJobs(cid: string): Promise<{
  ok?: boolean;
  series_id?: string;
  stage?: string;
  next_episode?: string;
  jobs?: JobSnap[];
  episodes?: EpisodeProgress[];
  events?: JobEventRow[];
  s2?: StatusPayload["s2"];
}> {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${cid}/jobs`));
}

export function episodeMasterUrl(cid: string, episodeId: string) {
  return `${BASE}/conversations/${cid}/episodes/${encodeURIComponent(episodeId)}/master`;
}

export function episodeShotVideoUrl(
  cid: string,
  episodeId: string,
  shotId: string,
) {
  return `${BASE}/conversations/${cid}/episodes/${encodeURIComponent(episodeId)}/shots/${encodeURIComponent(shotId)}/video`;
}

export async function regenerateShot(
  cid: string,
  episodeId: string,
  shotId: string,
  note?: string,
) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/episodes/${encodeURIComponent(episodeId)}/shots/${encodeURIComponent(shotId)}/regenerate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note || null, run_in_background: true }),
      },
    ),
  );
}

export async function rebuildMaster(cid: string, episodeId: string) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/episodes/${encodeURIComponent(episodeId)}/rebuild-master`,
      { method: "POST" },
    ),
  );
}

export async function cancelJobs(
  cid: string,
  opts?: { jobId?: string; episodeId?: string },
) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/jobs/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: opts?.jobId,
        episode_id: opts?.episodeId,
      }),
    }),
  );
}

export async function resumeJobs(
  cid: string,
  opts?: { episodeId?: string; fromShot?: string; force?: boolean },
) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/jobs/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        episode_id: opts?.episodeId,
        from_shot: opts?.fromShot,
        force: opts?.force ?? false,
        run_in_background: true,
      }),
    }),
  );
}

export async function listBible(cid: string) {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${cid}/bible`));
}

export async function getBibleDoc(cid: string, fileName: string) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/bible/${encodeURIComponent(fileName)}`,
    ),
  );
}

export async function saveBibleDoc(
  cid: string,
  fileName: string,
  content: string,
  preserveFormat = true,
) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/bible/${encodeURIComponent(fileName)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          preserve_format: preserveFormat,
        }),
      },
    ),
  );
}

export async function listLiterary(cid: string) {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${cid}/literary`));
}

export async function getLiteraryEpisode(cid: string, episodeId: string) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}`),
  );
}

export async function saveLiteraryEpisode(
  cid: string,
  episodeId: string,
  content: string,
) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    ),
  );
}

export async function getEpisodeFirstFrame(cid: string, episodeId: string) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}/first-frame`,
    ),
  );
}

export function episodeFirstFrameImageUrl(
  cid: string,
  episodeId: string,
  bust?: number | string,
) {
  const base = `${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}/first-frame/image`;
  return bust != null ? `${base}?t=${bust}` : base;
}

export async function uploadEpisodeFirstFrame(
  cid: string,
  episodeId: string,
  file: File,
) {
  const fd = new FormData();
  fd.append("file", file);
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}/first-frame`,
      { method: "POST", body: fd },
    ),
  );
}

export async function clearEpisodeFirstFrame(cid: string, episodeId: string) {
  return jsonOrThrow(
    await fetch(
      `${BASE}/conversations/${cid}/literary/${encodeURIComponent(episodeId)}/first-frame`,
      { method: "DELETE" },
    ),
  );
}

export async function listCast(cid: string) {
  return jsonOrThrow(await fetch(`${BASE}/conversations/${cid}/cast`));
}

export function castImageUrl(cid: string, character: string) {
  return `${BASE}/conversations/${cid}/cast/${encodeURIComponent(character)}/image`;
}

export async function uploadCastImage(
  cid: string,
  character: string,
  file: File,
) {
  const fd = new FormData();
  fd.append("character", character);
  fd.append("file", file);
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/cast/upload`, {
      method: "POST",
      body: fd,
    }),
  );
}

export async function generateCastImage(
  cid: string,
  body: { character: string; appearance: string; style?: string },
) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/cast/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function addCastCharacter(
  cid: string,
  body: { character: string; appearance?: string },
) {
  return jsonOrThrow(
    await fetch(`${BASE}/conversations/${cid}/cast/characters`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export type LlmSettings = {
  api_key: string;
  base_url: string;
  model: string;
};

export type WorkflowSettings = {
  comfyui_url: string;
  comfyui_api_key?: string | null;
  runninghub_api_key?: string | null;
  runninghub_concurrent_limit?: number;
  runninghub_instance_type?: string | null;
  image_default_workflow?: string | null;
  image_reference_workflow?: string | null;
  video_default_workflow?: string | null;
  tts_default_workflow?: string | null;
  aspect?: string;
};

export type LlmPreset = {
  name: string;
  base_url: string;
  model: string;
  api_key_url?: string;
  default_api_key?: string;
};

export type HermesSettings = {
  llm: LlmSettings;
  workflow: WorkflowSettings;
  presets: LlmPreset[];
  configured?: boolean;
  video_workflow_options?: string[];
  image_workflow_options?: string[];
  aspect_options?: string[];
};

export async function getSettings(): Promise<HermesSettings> {
  return jsonOrThrow(await fetch(`${BASE}/settings`));
}

export async function putSettings(body: {
  llm?: LlmSettings;
  workflow?: WorkflowSettings;
  apply_to_conversation_id?: string;
}): Promise<HermesSettings> {
  return jsonOrThrow(
    await fetch(`${BASE}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function resetSettings(): Promise<HermesSettings> {
  return jsonOrThrow(
    await fetch(`${BASE}/settings/reset`, { method: "POST" }),
  );
}

export async function testLlm(api_key: string, base_url: string): Promise<{
  ok: boolean;
  message: string;
  models: string[];
}> {
  return jsonOrThrow(
    await fetch(`${BASE}/settings/test_llm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, base_url }),
    }),
  );
}

export async function loadModels(api_key: string, base_url: string): Promise<{
  ok: boolean;
  message: string;
  models: string[];
}> {
  return jsonOrThrow(
    await fetch(`${BASE}/settings/load_models`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key, base_url }),
    }),
  );
}

export async function testComfyui(comfyui_url: string): Promise<{
  ok: boolean;
  message: string;
  models: string[];
}> {
  return jsonOrThrow(
    await fetch(`${BASE}/settings/test_comfyui`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comfyui_url }),
    }),
  );
}
