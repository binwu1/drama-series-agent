import { useState, type FormEvent } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreate: (title: string, premise?: string) => Promise<void>;
};

export function NewChatModal({ open, onClose, onCreate }: Props) {
  const [title, setTitle] = useState("");
  const [premise, setPremise] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const t = title.trim();
    if (!t) {
      setError("请填写系列标题");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onCreate(t, premise.trim() || undefined);
      setTitle("");
      setPremise("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form
        className="modal"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h2>新建系列对话</h2>
        <label>
          系列标题
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：七龙珠续集"
            autoFocus
          />
        </label>
        <label>
          可选梗概
          <textarea
            value={premise}
            onChange={(e) => setPremise(e.target.value)}
            placeholder="一句话设定（可选）"
            rows={3}
          />
        </label>
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="ghost" onClick={onClose} disabled={busy}>
            取消
          </button>
          <button type="submit" disabled={busy}>
            {busy ? "创建中…" : "创建"}
          </button>
        </div>
      </form>
    </div>
  );
}
