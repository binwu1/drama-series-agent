import { useEffect, useState } from "react";
import {
  cancelJobs,
  episodeMasterUrl,
  episodeShotVideoUrl,
  getJobs,
  rebuildMaster,
  regenerateShot,
  resumeJobs,
  type EpisodeProgress,
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

const STATUS_ZH: Record<string, string> = {
  complete: "已完成",
  partial: "部分完成",
  rendering: "渲染中",
  interrupted: "已中断",
  pending: "待渲染",
  no_jsonl: "尚无分镜表",
};

function kindLabel(kind?: string) {
  if (!kind) return "任务";
  return KIND_ZH[kind] || kind;
}

function pct(n?: number) {
  if (n == null || Number.isNaN(n)) return 0;
  return Math.round(Math.min(1, Math.max(0, n)) * 100);
}

function statusLabel(s?: string) {
  if (!s) return "—";
  return STATUS_ZH[s] || s;
}

export function JobsPage({ conversationId }: Props) {
  const [stage, setStage] = useState("");
  const [jobs, setJobs] = useState<JobSnap[]>([]);
  const [episodes, setEpisodes] = useState<EpisodeProgress[]>([]);
  const [events, setEvents] = useState<JobEventRow[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [regenNotes, setRegenNotes] = useState<Record<string, string>>({});
  const [previewShot, setPreviewShot] = useState<{
    episodeId: string;
    shotId: string;
  } | null>(null);

  async function refresh() {
    const data = await getJobs(conversationId);
    setStage(data.stage || "");
    setJobs(data.jobs || []);
    setEpisodes(data.episodes || []);
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
    const timer = window.setInterval(() => void tick(), 2500);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const running = jobs.some((j) =>
    ["queued", "running"].includes(String(j.status || "")),
  );

  async function onCancelEpisode(episodeId: string) {
    setBusy(`cancel:${episodeId}`);
    setNote("");
    setError("");
    try {
      const res = await cancelJobs(conversationId, { episodeId });
      setNote(String(res.message || `已请求中断 ${episodeId}`));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function onResumeEpisode(ep: EpisodeProgress) {
    const fromShot = ep.continue_from_shot || ep.resume_from_shot || undefined;
    setBusy(`resume:${ep.episode_id}`);
    setNote("");
    setError("");
    try {
      const res = await resumeJobs(conversationId, {
        episodeId: ep.episode_id,
        fromShot: fromShot || undefined,
      });
      setNote(String(res.message || `已续跑 ${ep.episode_id}`));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function onRegenerate(
    episodeId: string,
    shotId: string,
  ) {
    const key = `${episodeId}:${shotId}`;
    setBusy(`regen:${key}`);
    setNote("");
    setError("");
    try {
      const res = await regenerateShot(
        conversationId,
        episodeId,
        shotId,
        regenNotes[key],
      );
      setNote(String(res.message || `已入队重渲 ${shotId}`));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function onRebuildMaster(episodeId: string) {
    setBusy(`rebuild:${episodeId}`);
    setNote("");
    setError("");
    try {
      const res = await rebuildMaster(conversationId, episodeId);
      setNote(String(res.message || `已重新拼接 ${episodeId}`));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const jobsByEp = jobs.reduce<Record<string, JobSnap[]>>((acc, j) => {
    const ep = String(j.episode_id || "_other");
    (acc[ep] ||= []).push(j);
    return acc;
  }, {});

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
            {running ? " · 有任务进行中" : ""}
          </span>
        </div>
      </header>
      <div className="jobs-body">
        <p className="muted">
          按剧集查看分镜完成度。每集可单独中断 / 断点续跑；全部镜头完成后可下载成片、预览分镜，并对不满意的镜头重渲后自动重新拼接。
        </p>
        {error && <div className="modal-error">{error}</div>}
        {note && <p className="jobs-note">{note}</p>}

        {episodes.length === 0 && jobs.length === 0 ? (
          <p className="muted">
            还没有生成任务。在聊天里告诉 Agent「出片第N集」后，进度会按集显示在这里。
          </p>
        ) : (
          <div className="episode-job-list">
            {episodes.map((ep) => {
              const epJobs = jobsByEp[ep.episode_id] || [];
              const epRunning = epJobs.some((j) =>
                ["queued", "running"].includes(String(j.status || "")),
              );
              const canResume = Boolean(
                ep.continue_from_shot &&
                  !ep.all_shots_complete &&
                  ep.jsonl_exists &&
                  !epRunning,
              );
              const donePct =
                ep.shot_total && ep.shot_total > 0
                  ? Math.round(
                      ((ep.shot_done || 0) / ep.shot_total) * 100,
                    )
                  : 0;

              return (
                <section key={ep.episode_id} className="episode-job-card">
                  <div className="episode-job-head">
                    <div>
                      <h3>{ep.episode_id}</h3>
                      <span className="muted">
                        {statusLabel(ep.progress_status)} ·{" "}
                        {ep.shot_done ?? 0}/{ep.shot_total ?? 0} 镜
                        {ep.continue_from_shot
                          ? ` · 续跑点 ${ep.continue_from_shot}`
                          : ""}
                      </span>
                    </div>
                    <div className="episode-job-actions">
                      <button
                        type="button"
                        className="ghost tiny"
                        disabled={!!busy || !epRunning}
                        onClick={() => void onCancelEpisode(ep.episode_id)}
                      >
                        {busy === `cancel:${ep.episode_id}` ? "…" : "中断"}
                      </button>
                      <button
                        type="button"
                        className="tiny"
                        disabled={!!busy || !canResume}
                        onClick={() => void onResumeEpisode(ep)}
                        title={
                          ep.continue_from_shot
                            ? `从 ${ep.continue_from_shot} 续跑`
                            : "无可续跑镜头"
                        }
                      >
                        {busy === `resume:${ep.episode_id}`
                          ? "…"
                          : "断点续跑"}
                      </button>
                      {ep.all_shots_complete && (
                        <>
                          <a
                            className={`btn-like tiny ${ep.master_ready ? "" : "disabled"}`}
                            href={
                              ep.master_ready
                                ? episodeMasterUrl(
                                    conversationId,
                                    ep.episode_id,
                                  )
                                : undefined
                            }
                            download={
                              ep.master_ready
                                ? `${ep.episode_id}_master.mp4`
                                : undefined
                            }
                            onClick={(e) => {
                              if (!ep.master_ready) e.preventDefault();
                            }}
                          >
                            下载成片
                          </a>
                          <button
                            type="button"
                            className="ghost tiny"
                            disabled={!!busy || !ep.all_shots_complete}
                            onClick={() =>
                              void onRebuildMaster(ep.episode_id)
                            }
                          >
                            {busy === `rebuild:${ep.episode_id}`
                              ? "…"
                              : "重拼成片"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="job-bar">
                    <div
                      className="job-bar-fill"
                      style={{ width: `${donePct}%` }}
                    />
                  </div>

                  {epJobs.length > 0 && (
                    <ul className="job-cards nested">
                      {epJobs.map((j) => (
                        <li key={String(j.job_id)} className="job-card">
                          <div className="job-card-head">
                            <strong>{kindLabel(j.job_kind)}</strong>
                            <span className="muted">
                              {j.status || j.phase || "—"}
                            </span>
                          </div>
                          <div className="job-bar">
                            <div
                              className="job-bar-fill"
                              style={{ width: `${pct(j.progress)}%` }}
                            />
                          </div>
                          <div className="muted">
                            {pct(j.progress)}%
                            {j.shot_id ? ` · ${j.shot_id}` : ""}
                            {j.index != null
                              ? ` · ${j.index}/${j.total ?? "?"}`
                              : ""}
                          </div>
                          {j.error && (
                            <p className="modal-error">{j.error}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}

                  {(ep.all_shots_complete || (ep.shot_done || 0) > 0) &&
                    (ep.shots || []).length > 0 && (
                      <div className="shot-grid">
                        <h4>分镜预览</h4>
                        <ul className="shot-list">
                          {(ep.shots || []).map((s) => {
                            const key = `${ep.episode_id}:${s.shot_id}`;
                            const previewing =
                              previewShot?.episodeId === ep.episode_id &&
                              previewShot?.shotId === s.shot_id;
                            return (
                              <li key={s.shot_id} className="shot-row">
                                <div className="shot-row-head">
                                  <strong>{s.shot_id}</strong>
                                  <span className="muted">
                                    {s.complete
                                      ? "已完成"
                                      : s.has_video
                                        ? "缺尾帧"
                                        : "未生成"}
                                    {s.duration_seconds != null
                                      ? ` · ${s.duration_seconds}s`
                                      : ""}
                                  </span>
                                </div>
                                {s.has_video && (
                                  <>
                                    <button
                                      type="button"
                                      className="ghost tiny"
                                      onClick={() =>
                                        setPreviewShot(
                                          previewing
                                            ? null
                                            : {
                                                episodeId: ep.episode_id,
                                                shotId: s.shot_id,
                                              },
                                        )
                                      }
                                    >
                                      {previewing ? "收起预览" : "预览"}
                                    </button>
                                    {previewing && (
                                      <video
                                        className="shot-video"
                                        controls
                                        src={episodeShotVideoUrl(
                                          conversationId,
                                          ep.episode_id,
                                          s.shot_id,
                                        )}
                                      />
                                    )}
                                  </>
                                )}
                                {ep.all_shots_complete && s.complete && (
                                  <div className="shot-regen">
                                    <input
                                      type="text"
                                      placeholder="不满意的原因 / 修改要求（可选）"
                                      value={regenNotes[key] || ""}
                                      onChange={(e) =>
                                        setRegenNotes((prev) => ({
                                          ...prev,
                                          [key]: e.target.value,
                                        }))
                                      }
                                    />
                                    <button
                                      type="button"
                                      className="tiny"
                                      disabled={!!busy || epRunning}
                                      onClick={() =>
                                        void onRegenerate(
                                          ep.episode_id,
                                          s.shot_id,
                                        )
                                      }
                                    >
                                      {busy === `regen:${key}`
                                        ? "…"
                                        : "重渲此镜"}
                                    </button>
                                  </div>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}
                </section>
              );
            })}

            {(jobsByEp._other || []).length > 0 && (
              <section className="episode-job-card">
                <h3>其他任务</h3>
                <ul className="job-cards nested">
                  {(jobsByEp._other || []).map((j) => (
                    <li key={String(j.job_id)} className="job-card">
                      <div className="job-card-head">
                        <strong>{kindLabel(j.job_kind)}</strong>
                        <span className="muted">
                          {j.status || j.phase || "—"}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
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
                    {e.episode_id ? ` · ${e.episode_id}` : ""}
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
