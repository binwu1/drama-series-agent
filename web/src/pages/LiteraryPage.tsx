import { useEffect, useRef, useState } from "react";
import {
  acceptLiterary,
  clearEpisodeFirstFrame,
  episodeFirstFrameImageUrl,
  getEpisodeFirstFrame,
  getLiteraryEpisode,
  listLiterary,
  saveLiteraryEpisode,
  uploadEpisodeFirstFrame,
} from "../api";
import { goChat, goLiterary } from "../routing";

type Props = {
  conversationId: string;
  episodeId?: string;
};

type EpMeta = {
  episode_id: string;
  status?: string;
  status_zh?: string;
  has_user_first_frame?: boolean;
};

export function LiteraryPage({ conversationId, episodeId }: Props) {
  const [title, setTitle] = useState("");
  const [seriesId, setSeriesId] = useState("");
  const [episodes, setEpisodes] = useState<EpMeta[]>([]);
  const [activeEp, setActiveEp] = useState(episodeId || "");
  const [content, setContent] = useState("");
  const [statusZh, setStatusZh] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [mtimeHint, setMtimeHint] = useState("");
  const [hasUserFrame, setHasUserFrame] = useState(false);
  const [frameHint, setFrameHint] = useState("");
  const [frameBust, setFrameBust] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void (async () => {
      setError("");
      try {
        const data = await listLiterary(conversationId);
        setTitle(data.title || data.series_id || "");
        setSeriesId(data.series_id || "");
        const eps = (data.episodes || []) as EpMeta[];
        setEpisodes(eps);
        const pick = episodeId || eps[0]?.episode_id || "";
        setActiveEp(pick);
        if (pick && pick !== episodeId) {
          goLiterary(conversationId, pick);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [conversationId, episodeId]);

  useEffect(() => {
    if (!activeEp) {
      setContent("");
      setHasUserFrame(false);
      setFrameHint("");
      return;
    }
    void (async () => {
      setBusy(true);
      setError("");
      setOkMsg("");
      try {
        const [ep, frame] = await Promise.all([
          getLiteraryEpisode(conversationId, activeEp),
          getEpisodeFirstFrame(conversationId, activeEp),
        ]);
        setContent(ep.content || "");
        setStatusZh(ep.status_zh || ep.status || "");
        setTitle(ep.title || title);
        setSeriesId(ep.series_id || seriesId);
        setMtimeHint(ep.mtime ? String(ep.mtime) : "");
        setDirty(false);
        setHasUserFrame(Boolean(frame.has_user_upload));
        setFrameHint(String(frame.priority_hint || ""));
        setFrameBust(Date.now());
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, activeEp]);

  // Soft refresh when Agent regenerates while page is open
  useEffect(() => {
    if (!activeEp || dirty) return;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const ep = await getLiteraryEpisode(conversationId, activeEp);
          const next = ep.content || "";
          if (next && next !== content) {
            setContent(next);
            setStatusZh(ep.status_zh || ep.status || "");
            setMtimeHint(ep.mtime ? String(ep.mtime) : mtimeHint);
            setOkMsg("检测到剧本已更新，已刷新");
            const data = await listLiterary(conversationId);
            setEpisodes((data.episodes || []) as EpMeta[]);
          }
        } catch {
          /* ignore */
        }
      })();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [activeEp, conversationId, content, dirty, mtimeHint]);

  async function handleSave() {
    if (!activeEp) return;
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const ep = await saveLiteraryEpisode(conversationId, activeEp, content);
      setStatusZh(ep.status_zh || ep.status || "");
      setDirty(false);
      setOkMsg(
        "已保存（已同步 screenplay，并标记需重建 jsonl；下次出片会自动按新稿重建）",
      );
      const data = await listLiterary(conversationId);
      setEpisodes((data.episodes || []) as EpMeta[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleUploadFrame(file: File) {
    if (!activeEp) return;
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const res = await uploadEpisodeFirstFrame(conversationId, activeEp, file);
      setHasUserFrame(Boolean(res.has_user_upload));
      setFrameHint(String(res.priority_hint || frameHint));
      setFrameBust(Date.now());
      setOkMsg("已上传本集首帧（下次出片优先使用；已标记需重建）");
      const data = await listLiterary(conversationId);
      setEpisodes((data.episodes || []) as EpMeta[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleClearFrame() {
    if (!activeEp || !hasUserFrame) return;
    if (!window.confirm("清除本集用户首帧？将回退到上一集尾帧或默认开场。")) {
      return;
    }
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const res = await clearEpisodeFirstFrame(conversationId, activeEp);
      setHasUserFrame(Boolean(res.has_user_upload));
      setFrameHint(String(res.priority_hint || frameHint));
      setFrameBust(Date.now());
      setOkMsg("已清除用户首帧");
      const data = await listLiterary(conversationId);
      setEpisodes((data.episodes || []) as EpMeta[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="editor-page">
      <header className="editor-top">
        <button type="button" className="ghost" onClick={() => goChat()}>
          ← 返回聊天
        </button>
        <div className="editor-identity">
          <strong>{title || seriesId || "未命名系列"}</strong>
          <span className="muted">文学编辑 · 会话隔离 · Agent 写集会自动刷新</span>
        </div>
        <button
          type="button"
          className="ghost"
          disabled={busy || dirty || !activeEp}
          onClick={() =>
            void (async () => {
              if (!activeEp) return;
              setBusy(true);
              try {
                const [ep, frame] = await Promise.all([
                  getLiteraryEpisode(conversationId, activeEp),
                  getEpisodeFirstFrame(conversationId, activeEp),
                ]);
                setContent(ep.content || "");
                setStatusZh(ep.status_zh || ep.status || "");
                setMtimeHint(ep.mtime ? String(ep.mtime) : "");
                setHasUserFrame(Boolean(frame.has_user_upload));
                setFrameHint(String(frame.priority_hint || ""));
                setFrameBust(Date.now());
                setDirty(false);
                setOkMsg("已从磁盘刷新");
              } catch (err) {
                setError(err instanceof Error ? err.message : String(err));
              } finally {
                setBusy(false);
              }
            })()
          }
        >
          刷新
        </button>
        <button type="button" disabled={busy || !dirty} onClick={() => void handleSave()}>
          {busy ? "保存中…" : "保存"}
        </button>
        <button
          type="button"
          className="ghost"
          disabled={busy}
          onClick={() =>
            void (async () => {
              setBusy(true);
              setError("");
              try {
                await acceptLiterary(conversationId);
                setOkMsg("已确认验收文学包");
              } catch (err) {
                setError(err instanceof Error ? err.message : String(err));
              } finally {
                setBusy(false);
              }
            })()
          }
        >
          确认验收
        </button>
      </header>

      <div className="editor-layout">
        <aside className="editor-side">
          <h3>本系列剧集</h3>
          <p className="muted tiny">仅显示当前系列，不串剧</p>
          {episodes.length === 0 ? (
            <p className="muted">暂无剧集文件</p>
          ) : (
            <ul className="ep-nav">
              {episodes.map((ep) => (
                <li key={ep.episode_id}>
                  <button
                    type="button"
                    className={
                      ep.episode_id === activeEp ? "ep-nav-item active" : "ep-nav-item"
                    }
                    onClick={() => {
                      if (dirty && !window.confirm("有未保存修改，切换将丢失。继续？")) {
                        return;
                      }
                      setActiveEp(ep.episode_id);
                      goLiterary(conversationId, ep.episode_id);
                    }}
                  >
                    {ep.episode_id}
                    <span className="muted">
                      {" "}
                      {ep.status_zh || ep.status || ""}
                      {ep.has_user_first_frame ? " · 首帧✓" : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="editor-main">
          {activeEp ? (
            <>
              <div className="editor-meta">
                <h2>{activeEp}</h2>
                <span className="muted">{statusZh}</span>
              </div>

              <div className="ep-first-frame-band">
                <div className="ep-first-frame-thumb">
                  {hasUserFrame ? (
                    <img
                      src={episodeFirstFrameImageUrl(
                        conversationId,
                        activeEp,
                        frameBust,
                      )}
                      alt={`${activeEp} 首帧`}
                    />
                  ) : (
                    <div className="ep-first-frame-empty">未上传</div>
                  )}
                </div>
                <div className="ep-first-frame-meta">
                  <strong>本集首帧</strong>
                  <p className="muted tiny">
                    优先级：{frameHint || "用户上传 > 上一集尾帧 / 默认开场"}
                  </p>
                  <p className="muted tiny">
                    {hasUserFrame
                      ? "当前：用户上传（出片时优先）"
                      : "当前：未上传（将使用上一集尾帧或默认开场）"}
                  </p>
                  <div className="ep-first-frame-actions">
                    <input
                      ref={fileRef}
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      hidden
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void handleUploadFrame(f);
                        e.target.value = "";
                      }}
                    />
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={() => fileRef.current?.click()}
                    >
                      {hasUserFrame ? "更换" : "上传"}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy || !hasUserFrame}
                      onClick={() => void handleClearFrame()}
                    >
                      清除
                    </button>
                  </div>
                </div>
              </div>

              <textarea
                className="literary-editor"
                value={content}
                onChange={(e) => {
                  setContent(e.target.value);
                  setDirty(true);
                }}
                spellCheck={false}
              />
            </>
          ) : (
            <p className="muted">选择或生成一集后再编辑</p>
          )}
          {error && <div className="modal-error">{error}</div>}
          {okMsg && <div className="modal-ok">{okMsg}</div>}
        </main>
      </div>
    </div>
  );
}
