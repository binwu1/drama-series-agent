import { useEffect, useRef, useState } from "react";
import {
  acceptCast,
  addCastCharacter,
  castImageUrl,
  generateCastImage,
  listCast,
  uploadCastImage,
} from "../api";
import { goChat } from "../routing";

type Props = {
  conversationId: string;
};

type Asset = {
  name: string;
  role?: string;
  status?: string;
  status_zh?: string;
  appearance?: string;
  has_draft?: boolean;
  has_final?: boolean;
  draft_path?: string | null;
  final_path?: string | null;
  preview_path?: string | null;
  image_url?: string | null;
};

export function CastPage({ conversationId }: Props) {
  const [title, setTitle] = useState("");
  const [seriesId, setSeriesId] = useState("");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [appearance, setAppearance] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [bust, setBust] = useState(0);
  const [imgError, setImgError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  function hasImage(a?: Asset | null) {
    if (!a) return false;
    return Boolean(
      a.has_draft ||
        a.has_final ||
        a.draft_path ||
        a.final_path ||
        a.preview_path ||
        a.image_url,
    );
  }

  async function refresh(preferName?: string) {
    const data = await listCast(conversationId);
    setTitle(data.title || data.series_id || "");
    setSeriesId(data.series_id || "");
    const list = (data.assets || []) as Asset[];
    setAssets(list);
    const pick = preferName || (creating ? "" : selected) || list[0]?.name || "";
    if (pick) {
      setSelected(pick);
      setCreating(false);
      setNameInput(pick);
      const cur = list.find((a) => a.name === pick);
      setAppearance(cur?.appearance || "");
    }
    setImgError("");
  }

  useEffect(() => {
    void (async () => {
      setError("");
      try {
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  function startCreate() {
    setCreating(true);
    setSelected("");
    setNameInput("");
    setAppearance("");
    setOkMsg("");
    setError("");
    setImgError("");
    setTimeout(() => nameRef.current?.focus(), 50);
  }

  function selectCharacter(name: string) {
    setCreating(false);
    setSelected(name);
    setNameInput(name);
    const cur = assets.find((a) => a.name === name);
    setAppearance(cur?.appearance || "");
    setImgError("");
    setBust(Date.now());
  }

  async function handleAddCharacter() {
    const name = nameInput.trim();
    if (!name) {
      setError("请填写角色名");
      return;
    }
    setBusy("add");
    setError("");
    setOkMsg("");
    try {
      await addCastCharacter(conversationId, {
        character: name,
        appearance: appearance.trim(),
      });
      setOkMsg(`已新增角色「${name}」`);
      setCreating(false);
      setSelected(name);
      await refresh(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleUpload(file: File) {
    const name = (creating ? nameInput : selected || nameInput).trim();
    if (!name) {
      setError("请先选择或新增角色");
      return;
    }
    setBusy("upload");
    setError("");
    setOkMsg("");
    try {
      if (creating || !assets.some((a) => a.name === name)) {
        await addCastCharacter(conversationId, {
          character: name,
          appearance: appearance.trim(),
        });
      }
      await uploadCastImage(conversationId, name, file);
      setOkMsg(`已上传「${name}」草稿图`);
      setCreating(false);
      setSelected(name);
      setNameInput(name);
      setBust(Date.now());
      setImgError("");
      await refresh(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleGenerate() {
    const name = (creating ? nameInput : selected || nameInput).trim();
    if (!name) {
      setError("请先选择或新增角色");
      return;
    }
    if (!appearance.trim()) {
      setError("请填写角色外貌描述");
      return;
    }
    setBusy("gen");
    setError("");
    setOkMsg("");
    try {
      const res = await generateCastImage(conversationId, {
        character: name,
        appearance: appearance.trim(),
      });
      setOkMsg(res.message || `已生成「${name}」`);
      setCreating(false);
      setSelected(name);
      setNameInput(name);
      setBust(Date.now());
      setImgError("");
      await refresh(name);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const current = assets.find((a) => a.name === selected);
  const previewName = selected || (creating ? "" : nameInput.trim());
  const showPreview = Boolean(previewName && hasImage(current));

  return (
    <div className="editor-page">
      <header className="editor-top">
        <button type="button" className="ghost" onClick={() => goChat()}>
          ← 返回聊天
        </button>
        <div className="editor-identity">
          <strong>{title || seriesId || "未命名系列"}</strong>
          <span className="muted">角色图 · 会话隔离 · Flux / 上传</span>
        </div>
        <button
          type="button"
          className="ghost"
          disabled={!!busy}
          onClick={() => void refresh().catch((e) => setError(String(e)))}
        >
          刷新
        </button>
        <button
          type="button"
          disabled={!!busy}
          onClick={() =>
            void (async () => {
              setBusy("accept");
              setError("");
              try {
                await acceptCast(conversationId);
                setOkMsg("已确认验收角色图");
              } catch (err) {
                setError(err instanceof Error ? err.message : String(err));
              } finally {
                setBusy(null);
              }
            })()
          }
        >
          {busy === "accept" ? "…" : "确认验收"}
        </button>
      </header>

      <div className="editor-layout">
        <aside className="editor-side">
          <div className="side-head">
            <h3>本系列角色</h3>
            <button
              type="button"
              className="ghost tiny"
              onClick={startCreate}
              disabled={!!busy}
            >
              + 新增
            </button>
          </div>
          <p className="muted tiny">仅当前系列，不串剧</p>
          <button
            type="button"
            className="add-char-btn"
            onClick={startCreate}
            disabled={!!busy}
          >
            + 新增角色
          </button>
          {assets.length === 0 ? (
            <p className="muted">暂无角色</p>
          ) : (
            <ul className="ep-nav">
              {assets.map((a) => (
                <li key={a.name}>
                  <button
                    type="button"
                    className={
                      !creating && a.name === selected
                        ? "ep-nav-item active"
                        : "ep-nav-item"
                    }
                    onClick={() => selectCharacter(a.name)}
                  >
                    {a.name}
                    <span className="muted">
                      {" "}
                      {hasImage(a) ? "有图" : a.status_zh || a.status || ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="editor-main cast-main">
          <div className="cast-form">
            {creating && (
              <div className="create-banner">正在新增角色 — 填写名称后保存，或直接生成/上传</div>
            )}
            <label>
              角色名
              <input
                ref={nameRef}
                value={creating ? nameInput : selected || nameInput}
                onChange={(e) => {
                  if (!creating) setCreating(true);
                  setSelected("");
                  setNameInput(e.target.value);
                }}
                placeholder="例如：孙悟空"
              />
            </label>
            <label>
              外貌描述（Flux 提示词）
              <textarea
                className="appearance-input"
                rows={5}
                value={appearance}
                onChange={(e) => setAppearance(e.target.value)}
                placeholder="例如：少年齐天大圣，金色头箍，红披风，猴脸人形，站立正面三视图风格"
              />
            </label>
            <div className="cast-upload-row">
              {creating && (
                <button
                  type="button"
                  className="ghost"
                  disabled={!!busy}
                  onClick={() => void handleAddCharacter()}
                >
                  {busy === "add" ? "保存中…" : "保存角色名"}
                </button>
              )}
              <button
                type="button"
                disabled={!!busy}
                onClick={() => void handleGenerate()}
              >
                {busy === "gen" ? "Flux 生成中…" : "Flux 生成草稿图"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleUpload(f);
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                className="ghost"
                disabled={!!busy}
                onClick={() => fileRef.current?.click()}
              >
                {busy === "upload" ? "上传中…" : "手动上传图片"}
              </button>
            </div>
          </div>

          <div className="editor-meta">
            <h2>{current?.name || selected || nameInput || "预览"}</h2>
            {current && (
              <span className="muted">
                {current.role || "—"} · {hasImage(current) ? "有图" : current.status_zh || current.status}
              </span>
            )}
          </div>
          <div className="cast-preview-wrap">
            {showPreview && previewName ? (
              <img
                className="cast-preview"
                src={`${castImageUrl(conversationId, previewName)}?t=${bust}`}
                alt={previewName}
                onError={() =>
                  setImgError("图片加载失败，请点刷新或重新上传")
                }
                onLoad={() => setImgError("")}
              />
            ) : (
              <div className="cast-empty">
                暂无图片 — 点「+ 新增角色」或左侧角色，再 Flux 生成 / 手动上传
              </div>
            )}
          </div>

          {imgError && <div className="modal-error">{imgError}</div>}
          {error && <div className="modal-error">{error}</div>}
          {okMsg && <div className="modal-ok">{okMsg}</div>}
        </main>
      </div>
    </div>
  );
}
