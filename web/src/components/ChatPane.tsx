import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChatMessage } from "../api";

type Props = {
  messages: ChatMessage[];
  sending: boolean;
  onSend: (text: string) => Promise<void>;
  disabled?: boolean;
};

export function ChatPane({ messages, sending, onSend, disabled }: Props) {
  const [text, setText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || sending || disabled) return;
    setText("");
    await onSend(t);
  }

  return (
    <div className="chat-pane">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">发送消息开始与 Hermes Agent 对话</div>
        )}
        {messages.map((m, i) => (
          <div key={`${m.role}-${i}-${m.ts || ""}`} className={`bubble ${m.role}`}>
            <div className="bubble-role">
              {m.role === "user" ? "你" : m.role === "assistant" ? "Hermes" : m.role}
            </div>
            <div className="bubble-content">{m.content}</div>
          </div>
        ))}
        {sending && <div className="bubble assistant typing">思考中…</div>}
        <div ref={bottomRef} />
      </div>
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={disabled ? "请先选择或新建系列" : "输入指令，例如：现在进度？"}
          disabled={sending || disabled}
        />
        <button type="submit" disabled={sending || disabled || !text.trim()}>
          发送
        </button>
      </form>
    </div>
  );
}
