import { useEffect, useState } from "react";
import { getConversation, type StatusPayload } from "../api";
import { goBible, goCast, goJobs, goLiterary } from "../routing";

type Props = {
  conversationId: string | null;
  status: StatusPayload | null;
  forcedOpen?: boolean;
  onStatus: (s: StatusPayload) => void;
  onAssistantNote?: (text: string) => void;
};

type LitEp = {
  episode_id?: string;
  status?: string;
  status_zh?: string;
};

type CastAsset = {
  name?: string;
  role?: string;
  status?: string;
  status_zh?: string;
};

type EnrichJob = {
  job_id?: string;
  job_kind?: string;
  status?: string;
};

export function Workbench({
  conversationId,
  status,
  forcedOpen,
  onStatus,
}: Props) {
  const auto = Boolean(status?.open_workbench);
  const [pinned, setPinned] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const open = pinned || auto || Boolean(forcedOpen);

  useEffect(() => {
    if (auto) setPinned(true);
  }, [status?.series_id, auto]);

  if (!conversationId) return null;

  const gate = (status?.s1_gate || {}) as Record<string, unknown>;
  const jobs = status?.active_job_ids || [];
  const enrichJobs = (status?.enrich_jobs || []) as EnrichJob[];
  const literary = status?.artifacts?.literary;
  const cast = status?.artifacts?.cast;
  const episodes = (literary?.episodes || []) as LitEp[];
  const assets = (cast?.assets || []) as CastAsset[];
  const s2 = status?.s2;

  async function refresh() {
    setBusy("refresh");
    setError("");
    try {
      const detail = await getConversation(conversationId!);
      onStatus(detail.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <aside className={`workbench ${open ? "open" : "collapsed"}`}>
      <button
        type="button"
        className="workbench-toggle"
        onClick={() => setPinned((p) => (open ? false : !p))}
        title={open ? "收起工作台" : "展开工作台"}
      >
        {open ? "› 工作台" : "‹ 工作台"}
      </button>
      {open && (
        <div className="workbench-body">
          <div className="workbench-head">
            <h3>工作台</h3>
            <button
              type="button"
              className="ghost tiny"
              disabled={!!busy}
              onClick={() => void refresh()}
            >
              {busy === "refresh" ? "…" : "刷新"}
            </button>
          </div>

          <section className="wb-section">
            <h4>阶段状态</h4>
            <div className="wb-stage-line">
              {status?.stage || "—"} · 下一集 {status?.next_episode || "—"}
            </div>
            <ul className="gate-list">
              <li>文学 {gate.literary_accepted ? "✓ 已验收" : "… 待验收（在文学页确认）"}</li>
              <li>角色 {gate.cast_leads_accepted ? "✓ 已验收" : "… 待验收（在角色页确认）"}</li>
              <li>音频 {String(gate.audio_status || "missing")}</li>
              <li>S2 就绪 {gate.ready_for_s2 ? "✓" : "… 需文学+角色验收"}</li>
            </ul>
          </section>

          <section className="wb-section">
            <h4>生成进度</h4>
            <p className="muted">
              在聊天里说可以生成视频后，Agent 会自动构建并入队渲染。进度在独立页面查看。
            </p>
            <ul className="gate-list">
              <li>集号 {s2?.episode_id || status?.next_episode || "—"}</li>
              <li>工作流 {s2?.default_workflow || "未设置（系统配置里选择）"}</li>
              <li>画幅 {s2?.aspect || "9:16"}</li>
              <li>
                jsonl{" "}
                {s2?.jsonl_exists
                  ? `已有 · ${s2.shot_count ?? "?"} 镜 · ${s2.valid ? "校验通过" : "未通过"}`
                  : "尚未构建"}
              </li>
              <li>活跃任务 {jobs.length ? jobs.join("、") : "无"}</li>
            </ul>
            {s2?.errors && s2.errors.length > 0 && !s2.valid && (
              <p className="muted">{s2.errors[0]}</p>
            )}
            <button
              type="button"
              onClick={() => goJobs(conversationId!)}
            >
              打开生成进度页 →
            </button>
          </section>

          <section className="wb-section">
            <h4>系列设定</h4>
            <p className="muted">
              大纲 / 世界观 / 角色 / 画风 / 分集目录。可手改（保格式）或回聊天让 Agent 改。
            </p>
            {(() => {
              const bibleDocs =
                (status?.series_bible?.docs || []) as Array<{
                  file?: string;
                  label?: string;
                  ready?: boolean;
                }>;
              const readyN = bibleDocs.filter((d) => d.ready).length;
              return (
                <>
                  <ul className="gate-list">
                    <li>
                      圣经{" "}
                      {status?.series_bible?.bible_ready
                        ? `✓ 已齐（${readyN}/${bibleDocs.length || 5}）`
                        : `… 未齐（${readyN}/${bibleDocs.length || 5}）`}
                    </li>
                  </ul>
                  {bibleDocs.length > 0 && (
                    <ul className="wb-link-list">
                      {bibleDocs.map((d) => (
                        <li key={String(d.file)}>
                          <button
                            type="button"
                            className="linkish"
                            onClick={() =>
                              goBible(conversationId!, String(d.file))
                            }
                          >
                            {d.label || d.file}
                            <span className="muted">
                              {" "}
                              · {d.ready ? "已有" : "缺失"}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => goBible(conversationId!)}
                  >
                    打开系列设定页 →
                  </button>
                </>
              );
            })()}
          </section>

          <section className="wb-section">
            <h4>文学产出</h4>
            <p className="muted">在独立页面查看与修改（按系列隔离）</p>
            {episodes.length === 0 ? (
              <p className="muted">暂无剧本草稿</p>
            ) : (
              <ul className="wb-link-list">
                {episodes.map((ep) => (
                  <li key={String(ep.episode_id)}>
                    <button
                      type="button"
                      className="linkish"
                      onClick={() =>
                        goLiterary(conversationId!, String(ep.episode_id))
                      }
                    >
                      打开 {ep.episode_id}
                      <span className="muted">
                        {" "}
                        · {ep.status_zh || ep.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="ghost"
              onClick={() => goLiterary(conversationId!)}
            >
              打开文学编辑页 →
            </button>
          </section>

          <section className="wb-section">
            <h4>角色资产</h4>
            <p className="muted">大图预览与上传请进角色页</p>
            {assets.length === 0 ? (
              <p className="muted">暂无角色</p>
            ) : (
              <ul className="wb-link-list">
                {assets.slice(0, 8).map((a) => (
                  <li key={String(a.name)}>
                    {a.name}
                    <span className="muted">
                      {" "}
                      · {a.status_zh || a.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="ghost"
              onClick={() => goCast(conversationId!)}
            >
              打开角色图页 →
            </button>
          </section>

          <section className="wb-section">
            <h4>任务</h4>
            {jobs.length > 0 && (
              <ul className="gate-list">
                {jobs.map((j) => (
                  <li key={j}>{j}</li>
                ))}
              </ul>
            )}
            {enrichJobs.length === 0 && jobs.length === 0 ? (
              <p className="muted">暂无任务记录</p>
            ) : (
              <ul className="wb-job-history">
                {enrichJobs
                  .slice()
                  .reverse()
                  .map((j) => (
                    <li key={String(j.job_id)}>
                      <code>{j.job_kind || "job"}</code>{" "}
                      <span className="muted">{j.status}</span>
                    </li>
                  ))}
              </ul>
            )}
          </section>

          {error && <div className="modal-error">{error}</div>}
          <button type="button" className="ghost" onClick={() => setPinned(false)}>
            收起工作台
          </button>
        </div>
      )}
    </aside>
  );
}
