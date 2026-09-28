import { useEffect, useState } from "react";
import {
  acceptLiterary,
  getLiteraryEpisode,
  listLiterary,
  saveLiteraryEpisode,
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

  useEffect(() => {
    void (async () => {
      setError("");
      try {
        const data = await listLiterary(conversationId);
        setTitle(data.title || data.series_id || "");
        setSeriesId(data.series_id || "");
        const eps = (data.episodes || []) as EpMeta[];
        setEpisodes(eps);
        const pick =
          episodeId ||
          eps[0]?.episode_id ||
          "";
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
      return;
    }
    void (async () => {
      setBusy(true);
      setError("");
      setOkMsg("");
      try {
        const ep = await getLiteraryEpisode(conversationId, activeEp);
        setContent(ep.content || "");
        setStatusZh(ep.status_zh || ep.status || "");
        setTitle(ep.title || title);
        setSeriesId(ep.series_id || seriesId);
        setDirty(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, activeEp]);

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

  return (
    <div className="editor-page">
      <header className="editor-top">
        <button type="button" className="ghost" onClick={() => goChat()}>
          ← 返回聊天
        </button>
        <div className="editor-identity">
          <strong>{title || seriesId || "未命名系列"}</strong>
          <span className="muted">文学编辑 · 会话隔离</span>
        </div>
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
