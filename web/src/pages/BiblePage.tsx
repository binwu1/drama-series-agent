import { useCallback, useEffect, useState } from "react";
import { getBibleDoc, listBible, saveBibleDoc } from "../api";
import { goChat, goBible } from "../routing";

const CHAT_DRAFT_KEY = "hermes.chatDraft";

type Props = {
  conversationId: string;
  fileName?: string;
};

type DocMeta = {
  file: string;
  label?: string;
  ready?: boolean;
  path?: string;
};

const DOC_HINTS: Record<string, string> = {
  "creative-plan.md": "可改正文要点，请保留「## 数字. 标题」等原有章节标题。",
  "world.md": "可改规则与代价描述，请保留原有一级/二级标题。",
  "characters.md": "可改角色目标与关系，请保留各角色小节标题。",
  "art-style.md": "可改气质与关键词，请保留原有标题层级。",
  "episode-directory.md":
    "可改单元格内文字，请保留阶段标题与「| EPxxx |」表格列结构，勿删集号。",
};

export function BiblePage({ conversationId, fileName }: Props) {
  const [title, setTitle] = useState("");
  const [seriesId, setSeriesId] = useState("");
  const [docs, setDocs] = useState<DocMeta[]>([]);
  const [bibleReady, setBibleReady] = useState(false);
  const [activeFile, setActiveFile] = useState(fileName || "");
  const [content, setContent] = useState("");
  const [serverMtime, setServerMtime] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [agentNote, setAgentNote] = useState("");

  const loadList = useCallback(async () => {
    const data = await listBible(conversationId);
    setTitle(data.title || data.series_id || "");
    setSeriesId(data.series_id || "");
    setBibleReady(Boolean(data.bible_ready));
    const rows = (data.docs || []) as DocMeta[];
    setDocs(rows);
    return rows;
  }, [conversationId]);

  const loadDoc = useCallback(async (file: string) => {
    if (!file) {
      setContent("");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const doc = await getBibleDoc(conversationId, file);
      setContent(doc.content || "");
      setServerMtime(typeof doc.mtime === "number" ? doc.mtime : null);
      if (doc.title) setTitle(doc.title);
      if (doc.series_id) setSeriesId(doc.series_id);
      setDirty(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [conversationId]);

  useEffect(() => {
    void (async () => {
      setError("");
      try {
        const rows = await loadList();
        const pick =
          fileName ||
          rows.find((d) => d.ready)?.file ||
          rows[0]?.file ||
          "creative-plan.md";
        setActiveFile(pick);
        if (pick && pick !== fileName) {
          goBible(conversationId, pick);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, [conversationId, fileName, loadList]);

  useEffect(() => {
    if (!activeFile) return;
    void loadDoc(activeFile);
  }, [activeFile, loadDoc]);

  // Soft refresh from disk while idle (Agent may have rewritten files)
  useEffect(() => {
    if (!activeFile || dirty) return;
    const timer = window.setInterval(() => {
      void (async () => {
        try {
          const doc = await getBibleDoc(conversationId, activeFile);
          const mt = typeof doc.mtime === "number" ? doc.mtime : null;
          if (mt != null && serverMtime != null && mt > serverMtime + 0.01) {
            setContent(doc.content || "");
            setServerMtime(mt);
            setOkMsg("检测到 Agent/磁盘更新，已刷新当前文件");
            await loadList();
          }
        } catch {
          /* ignore poll errors */
        }
      })();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activeFile, conversationId, dirty, loadList, serverMtime]);

  async function handleSave() {
    if (!activeFile) return;
    setBusy(true);
    setError("");
    setOkMsg("");
    try {
      const doc = await saveBibleDoc(conversationId, activeFile, content, true);
      setContent(doc.content || "");
      setServerMtime(typeof doc.mtime === "number" ? doc.mtime : null);
      setDirty(false);
      setOkMsg(
        doc.hint ||
          "已保存（已校验：保留原有标题/表格结构）",
      );
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function askAgent() {
    const file = activeFile || "creative-plan.md";
    const note =
      agentNote.trim() ||
      `请用 save_series_bible_doc 修改 ${file}：……（只改正文要点，保留原有标题与表格结构，不要改文件格式）`;
    sessionStorage.setItem(CHAT_DRAFT_KEY, note);
    goChat();
  }

  return (
    <div className="editor-page">
      <header className="editor-top">
        <button type="button" className="ghost" onClick={() => goChat()}>
          ← 返回聊天
        </button>
        <div className="editor-identity">
          <strong>{title || seriesId || "未命名系列"}</strong>
          <span className="muted">
            系列设定 · {bibleReady ? "圣经已齐" : "圣经未齐"} · 可手改或让 Agent 改
          </span>
        </div>
        <button
          type="button"
          className="ghost"
          disabled={busy || dirty}
          onClick={() => void loadDoc(activeFile)}
        >
          刷新
        </button>
        <button
          type="button"
          disabled={busy || !dirty || !activeFile}
          onClick={() => void handleSave()}
        >
          {busy ? "保存中…" : "保存"}
        </button>
      </header>

      <div className="editor-layout">
        <aside className="editor-side">
          <h3>开发文件</h3>
          <p className="muted tiny">dramas/ 下系列圣经，按文件隔离</p>
          {docs.length === 0 ? (
            <p className="muted">暂无设定文件。可在聊天里说「确定大纲…」生成。</p>
          ) : (
            <ul className="ep-nav">
              {docs.map((d) => (
                <li key={d.file}>
                  <button
                    type="button"
                    className={
                      d.file === activeFile ? "ep-nav-item active" : "ep-nav-item"
                    }
                    onClick={() => {
                      if (dirty && !window.confirm("有未保存修改，切换将丢失。继续？")) {
                        return;
                      }
                      setActiveFile(d.file);
                      goBible(conversationId, d.file);
                    }}
                  >
                    {d.label || d.file}
                    <span className="muted">
                      {" "}
                      {d.ready ? "✓" : "…"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="bible-agent-box">
            <h4>让 Agent 改</h4>
            <p className="muted tiny">
              回聊天发送指令；Agent 会用 save_series_bible_doc 落盘，本页会自动刷新。
            </p>
            <textarea
              className="bible-agent-input"
              rows={4}
              value={agentNote}
              onChange={(e) => setAgentNote(e.target.value)}
              placeholder={`例如：把 ${activeFile || "creative-plan.md"} 里集数改成 20，并同步分集目录…`}
            />
            <button type="button" className="ghost" onClick={askAgent}>
              填入聊天并返回 →
            </button>
          </div>
        </aside>

        <main className="editor-main">
          {activeFile ? (
            <>
              <div className="editor-meta">
                <h2>{docs.find((d) => d.file === activeFile)?.label || activeFile}</h2>
                <span className="muted">{activeFile}</span>
              </div>
              <p className="bible-format-hint">
                {DOC_HINTS[activeFile] ||
                  "可修改正文内容；保存时会校验，禁止删除原有标题结构。"}
              </p>
              <textarea
                className="literary-editor bible-editor"
                value={content}
                onChange={(e) => {
                  setContent(e.target.value);
                  setDirty(true);
                  setOkMsg("");
                }}
                spellCheck={false}
                placeholder="文件尚未生成。请先在聊天中完成系列开发。"
              />
            </>
          ) : (
            <p className="muted">选择左侧文件后编辑</p>
          )}
          {error && <div className="modal-error">{error}</div>}
          {okMsg && <div className="modal-ok">{okMsg}</div>}
        </main>
      </div>
    </div>
  );
}
