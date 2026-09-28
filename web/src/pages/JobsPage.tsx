import { useEffect, useState } from "react";
import {
  cancelJobs,
  getJobs,
  resumeJobs,
  type JobEventRow,
  type JobSnap,
} from "../api";
import { goChat } from "../routing";

type Props = { conversationId: string };

const KIND_ZH: Record<string, string> = {
  literary_generate: "文学生成",
  cast_image_generate: "角色图",
  build_episode_jsonl: "构建 jsonl",
  comfy_episode: "视频渲染",
  export_package: "导出",
};

function kindLabel(kind?: string) {
  if (!kind) return "任务";
  return KIND_ZH[kind] || kind;
}

function pct(n?: number) {
  if (n == null || Number.isNaN(n)) return 0;
  return Math.round(Math.min(1, Math.max(0, n)) * 100);
}

export function JobsPage({ conversationId }: Props) {
  const [stage, setStage] = useState("");
  const [episode, setEpisode] = useState("");
  const [resumeShot, setResumeShot] = useState("");
  const [jobs, setJobs] = useState<JobSnap[]>([]);
  const [events, setEvents] = useState<JobEventRow[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  async function refresh() {
    const data = await getJobs(conversationId);
    setStage(data.stage || "");
    setEpisode(String(data.next_episode || data.s2?.episode_id || ""));
    setResumeShot(String(data.s2?.resume_from_shot || ""));
    setJobs(data.jobs || []);
    setEvents(data.events || []);
  }

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        await refresh();
        if (!stop) setError("");
      } catch (err) {
        if (!stop) setError(err instanceof Error ? err.message : String(err));
      }
    }
    void tick();
    const timer = window.setInterval(() => void tick(), 2000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const running = jobs.some((j) =>
    ["queued", "running"].includes(String(j.status || "")),
  );

  async function onCancel() {
    setBusy("cancel");
    setNote("");
    setError("");
    try {
      const res = await cancelJobs(conversationId, { episodeId: episode || undefined });
      setNote(String(res.message || "已请求中断"));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function onResume() {
    setBusy("resume");
    setNote("");
    setError("");
    try {
      const res = await resumeJobs(conversationId, {
        episodeId: episode || undefined,
        fromShot: resumeShot || undefined,
      });
      setNote(String(res.message || "已续跑"));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="editor-page">
      <header className="editor-top">
        <button type="button" className="ghost" onClick={() => goChat()}>
          ← 返回聊天
        </button>
        <div className="editor-identity">
          <strong>生成进度</strong>
          <span className="muted">
            {stage || "—"}
            {episode ? ` · ${episode}` : ""}
            {resumeShot ? ` · 断点 ${resumeShot}` : ""}
          </span>
        </div>
        <button
          type="button"
          className="ghost"
          disabled={!!busy || !running}
          onClick={() => void onCancel()}
        >
          {busy === "cancel" ? "…" : "中断"}
        </button>
        <button
          type="button"
          disabled={!!busy || running || !resumeShot}
          onClick={() => void onResume()}
        >
          {busy === "resume" ? "…" : "断点续跑"}
        </button>
      </header>
      <div className="jobs-body">
        <p className="muted">
          中断会在当前镜头采完后生效，并记下断点；之后可点「断点续跑」。
        </p>
        {error && <div className="modal-error">{error}</div>}
        {note && <p>{note}</p>}
        {jobs.length === 0 ? (
          <p className="muted">
            还没有生成任务。在聊天里告诉 Agent 可以生成视频后，进度会显示在这里。
          </p>
        ) : (
          <ul className="job-cards">
            {jobs.map((j) => (
              <li key={String(j.job_id)} className="job-card">
                <div className="job-card-head">
                  <strong>{kindLabel(j.job_kind)}</strong>
                  <span className="muted">
                    {j.episode_id || ""} · {j.status || j.phase || "—"}
                  </span>
                </div>
                <div className="job-bar">
                  <div className="job-bar-fill" style={{ width: `${pct(j.progress)}%` }} />
                </div>
                <div className="muted">
                  {pct(j.progress)}%
                  {j.shot_id ? ` · ${j.shot_id}` : ""}
                  {j.index != null ? ` · ${j.index}/${j.total ?? "?"}` : ""}
                </div>
                {j.error && <p className="modal-error">{j.error}</p>}
                {j.master_path && <p>成片：{j.master_path}</p>}
              </li>
            ))}
          </ul>
        )}
        <h3>近期事件</h3>
        {events.length === 0 ? (
          <p className="muted">暂无事件</p>
        ) : (
          <ul className="job-events">
            {events
              .slice()
              .reverse()
              .map((e, i) => (
                <li key={`${e.job_id || "e"}-${e.ts || i}`}>
                  <code>{e.event_type || e.phase || "event"}</code>
                  <span className="muted">
                    {" "}
                    {kindLabel(e.job_kind)}
                    {e.shot_id ? ` · ${e.shot_id}` : ""}
                    {e.message ? ` · ${e.message}` : ""}
                    {e.error ? ` · ${e.error}` : ""}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </div>
    </div>
  );
}
