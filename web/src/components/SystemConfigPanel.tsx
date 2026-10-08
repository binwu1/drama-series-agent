import { useEffect, useState } from "react";
import {
  getSettings,
  loadModels,
  putSettings,
  resetSettings,
  testComfyui,
  testLlm,
  type HermesSettings,
  type LlmPreset,
  type LlmSettings,
  type WorkflowSettings,
} from "../api";

const CUSTOM = "Custom";
const CUSTOM_MODEL = "✏️ 自定义...";

type Props = {
  /** Active conversation — save also writes series_runtime workflow/aspect */
  conversationId?: string | null;
  /** Called after successful save so chat can keep using fresh config */
  onSaved?: () => void;
};

const ASPECT_LABEL: Record<string, string> = {
  "9:16": "9:16 竖屏",
  "16:9": "16:9 横屏",
  "1:1": "1:1 方形",
};

export function SystemConfigPanel({ conversationId, onSaved }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [presets, setPresets] = useState<LlmPreset[]>([]);
  const [presetName, setPresetName] = useState(CUSTOM);
  const [llm, setLlm] = useState<LlmSettings>({
    api_key: "",
    base_url: "",
    model: "",
  });
  const [workflow, setWorkflow] = useState<WorkflowSettings>({
    comfyui_url: "http://127.0.0.1:8188",
    runninghub_concurrent_limit: 1,
    aspect: "9:16",
    video_default_workflow: "selfhost/video_minimax_h3_r2v_fast.json",
  });
  const [videoOptions, setVideoOptions] = useState<string[]>([]);
  const [imageOptions, setImageOptions] = useState<string[]>([]);
  const [aspectOptions, setAspectOptions] = useState<string[]>([
    "9:16",
    "16:9",
    "1:1",
  ]);
  const [loadedModels, setLoadedModels] = useState<string[]>([]);
  const [modelSelect, setModelSelect] = useState(CUSTOM_MODEL);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        const s = await getSettings();
        applyPayload(s);
        setExpanded(!s.configured);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setExpanded(true);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function applyPayload(s: HermesSettings) {
    setLlm(s.llm);
    setWorkflow({
      ...s.workflow,
      runninghub_concurrent_limit: s.workflow.runninghub_concurrent_limit ?? 1,
      aspect: s.workflow.aspect || "9:16",
      video_default_workflow:
        s.workflow.video_default_workflow ||
        "selfhost/video_minimax_h3_r2v_fast.json",
    });
    setPresets(s.presets || []);
    setConfigured(Boolean(s.configured));
    setVideoOptions(s.video_workflow_options || []);
    setImageOptions(s.image_workflow_options || []);
    setAspectOptions(s.aspect_options || ["9:16", "16:9", "1:1"]);
    const match = (s.presets || []).find(
      (p) => p.base_url === s.llm.base_url && p.model === s.llm.model,
    );
    setPresetName(match?.name || CUSTOM);
    if (s.llm.model) {
      setLoadedModels((prev) =>
        prev.includes(s.llm.model) ? prev : [s.llm.model, ...prev],
      );
      setModelSelect(s.llm.model);
    } else {
      setModelSelect(CUSTOM_MODEL);
    }
  }

  function applyPreset(name: string) {
    setPresetName(name);
    if (name === CUSTOM) return;
    const p = presets.find((x) => x.name === name);
    if (!p) return;
    setLlm((prev) => ({
      api_key:
        name === presetName
          ? prev.api_key
          : p.default_api_key || (prev.api_key ? prev.api_key : ""),
      base_url: p.base_url,
      model: p.model,
    }));
    setModelSelect(p.model);
    setLoadedModels((prev) =>
      prev.includes(p.model) ? prev : [p.model, ...prev],
    );
  }

  async function handleLoadModels() {
    setBusy("load");
    setError("");
    setOkMsg("");
    try {
      const res = await loadModels(llm.api_key, llm.base_url);
      if (!res.ok) {
        setError(res.message);
        return;
      }
      setLoadedModels(res.models);
      setOkMsg(res.message);
      if (res.models.length && !res.models.includes(llm.model)) {
        setLlm((prev) => ({ ...prev, model: res.models[0] }));
        setModelSelect(res.models[0]);
      } else if (llm.model) {
        setModelSelect(llm.model);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleTestLlm() {
    setBusy("test-llm");
    setError("");
    setOkMsg("");
    try {
      const res = await testLlm(llm.api_key, llm.base_url);
      if (res.ok) {
        setOkMsg(res.message);
        if (res.models.length) setLoadedModels(res.models);
      } else {
        setError(res.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleTestComfy() {
    setBusy("test-comfy");
    setError("");
    setOkMsg("");
    try {
      const res = await testComfyui(workflow.comfyui_url || "");
      if (res.ok) setOkMsg(res.message);
      else setError(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSave() {
    setBusy("save");
    setError("");
    setOkMsg("");
    const model =
      modelSelect === CUSTOM_MODEL ? llm.model.trim() : modelSelect;
    if (!llm.api_key || !llm.base_url || !model) {
      setError("请先完成大语言模型配置（API Key / Base URL / Model）");
      setBusy(null);
      return;
    }
    try {
      const s = await putSettings({
        llm: { ...llm, model },
        workflow,
        apply_to_conversation_id: conversationId || undefined,
      });
      applyPayload(s);
      setOkMsg(
        conversationId
          ? "配置已保存（含当前系列工作流 / 宽高比）"
          : "配置已保存",
      );
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleReset() {
    if (!window.confirm("确定重置为默认配置？")) return;
    setBusy("reset");
    setError("");
    setOkMsg("");
    try {
      const s = await resetSettings();
      applyPayload(s);
      setExpanded(true);
      setOkMsg("已重置为默认配置");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const presetLink = presets.find((p) => p.name === presetName)?.api_key_url;
  const modelOptions = [CUSTOM_MODEL, ...loadedModels.filter((m) => m !== CUSTOM_MODEL)];

  return (
    <div className={`sys-config ${expanded ? "open" : ""}`}>
      <button
        type="button"
        className="sys-config-toggle"
        onClick={() => setExpanded((v) => !v)}
      >
        <span>⚙️ 系统配置（必需）</span>
        <span className="sys-config-meta">
          {configured ? "已配置" : "未配置"} · {expanded ? "收起" : "展开"}
        </span>
      </button>

      {expanded && (
        <div className="sys-config-body">
          {!configured && (
            <div className="sys-config-warn">
              ⚠️ 请先完成系统配置才能正常调用 Agent
            </div>
          )}
          {loading ? (
            <p className="muted">加载中…</p>
          ) : (
            <>
              <div className="sys-config-grid">
                <section className="sys-card">
                  <h3>🤖 大语言模型</h3>
                  <label>
                    快速选择
                    <select
                      value={presetName}
                      onChange={(e) => applyPreset(e.target.value)}
                    >
                      {presets.map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.name}
                        </option>
                      ))}
                      <option value={CUSTOM}>{CUSTOM}</option>
                    </select>
                  </label>
                  {presetLink && (
                    <a
                      className="settings-link"
                      href={presetLink}
                      target="_blank"
                      rel="noreferrer"
                    >
                      🔑 获取 API Key
                    </a>
                  )}
                  <hr className="sys-hr" />
                  <label>
                    API Key *
                    <input
                      type="password"
                      value={llm.api_key}
                      onChange={(e) =>
                        setLlm((prev) => ({ ...prev, api_key: e.target.value }))
                      }
                      autoComplete="off"
                    />
                  </label>
                  <label>
                    Base URL *
                    <input
                      value={llm.base_url}
                      onChange={(e) => {
                        setPresetName(CUSTOM);
                        setLlm((prev) => ({
                          ...prev,
                          base_url: e.target.value,
                        }));
                      }}
                    />
                  </label>
                  <label>
                    Model *
                    <select
                      value={
                        modelOptions.includes(modelSelect)
                          ? modelSelect
                          : CUSTOM_MODEL
                      }
                      onChange={(e) => {
                        const v = e.target.value;
                        setModelSelect(v);
                        if (v !== CUSTOM_MODEL) {
                          setLlm((prev) => ({ ...prev, model: v }));
                        }
                      }}
                    >
                      {modelOptions.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </label>
                  {(modelSelect === CUSTOM_MODEL ||
                    !loadedModels.includes(modelSelect)) && (
                    <label>
                      自定义模型名称
                      <input
                        value={llm.model}
                        onChange={(e) => {
                          setPresetName(CUSTOM);
                          setModelSelect(CUSTOM_MODEL);
                          setLlm((prev) => ({
                            ...prev,
                            model: e.target.value,
                          }));
                        }}
                        placeholder="例如 qwen-max"
                      />
                    </label>
                  )}
                  <div className="sys-inline-actions">
                    <button
                      type="button"
                      className="ghost"
                      disabled={!!busy}
                      onClick={() => void handleLoadModels()}
                    >
                      {busy === "load" ? "加载中…" : "🔄 加载"}
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      disabled={!!busy}
                      onClick={() => void handleTestLlm()}
                    >
                      {busy === "test-llm" ? "测试中…" : "🔌 测试"}
                    </button>
                  </div>
                </section>

                <section className="sys-card">
                  <h3>🔧 ComfyUI 配置</h3>
                  <h4>本地/自建 ComfyUI</h4>
                  <div className="sys-row-2">
                    <label>
                      ComfyUI 服务器地址
                      <input
                        value={workflow.comfyui_url || ""}
                        onChange={(e) =>
                          setWorkflow((prev) => ({
                            ...prev,
                            comfyui_url: e.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      ComfyUI API 密钥
                      <input
                        type="password"
                        value={workflow.comfyui_api_key || ""}
                        onChange={(e) =>
                          setWorkflow((prev) => ({
                            ...prev,
                            comfyui_api_key: e.target.value,
                          }))
                        }
                        autoComplete="off"
                      />
                    </label>
                  </div>
                  <button
                    type="button"
                    className="ghost"
                    disabled={!!busy}
                    onClick={() => void handleTestComfy()}
                  >
                    {busy === "test-comfy" ? "测试中…" : "测试连接"}
                  </button>
                  <hr className="sys-hr" />
                  <h4>RunningHub 云端</h4>
                  <label>
                    RunningHub API 密钥
                    <input
                      type="password"
                      value={workflow.runninghub_api_key || ""}
                      onChange={(e) =>
                        setWorkflow((prev) => ({
                          ...prev,
                          runninghub_api_key: e.target.value,
                        }))
                      }
                      autoComplete="off"
                    />
                  </label>
                  <p className="muted">
                    没有本地 ComfyUI？可用 RunningHub 云端：
                    <a
                      className="settings-link"
                      href="https://www.runninghub.cn/?inviteCode=bozpdlbj"
                      target="_blank"
                      rel="noreferrer"
                    >
                      点此获取 RunningHub API Key
                    </a>
                  </p>
                  <div className="sys-row-2">
                    <label>
                      并发限制
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={workflow.runninghub_concurrent_limit ?? 1}
                        onChange={(e) =>
                          setWorkflow((prev) => ({
                            ...prev,
                            runninghub_concurrent_limit: Number(e.target.value) || 1,
                          }))
                        }
                      />
                    </label>
                    <label>
                      机器规格
                      <select
                        value={
                          workflow.runninghub_instance_type === "plus"
                            ? "plus"
                            : ""
                        }
                        onChange={(e) =>
                          setWorkflow((prev) => ({
                            ...prev,
                            runninghub_instance_type: e.target.value || null,
                          }))
                        }
                      >
                        <option value="">24G 显存</option>
                        <option value="plus">48G 显存</option>
                      </select>
                    </label>
                  </div>
                  <hr className="sys-hr" />
                  <h4>Hermes 出片 · 工作流与画幅</h4>
                  <label>
                    视频工作流
                    <select
                      value={
                        workflow.video_default_workflow ||
                        videoOptions[0] ||
                        ""
                      }
                      onChange={(e) =>
                        setWorkflow((prev) => ({
                          ...prev,
                          video_default_workflow: e.target.value,
                        }))
                      }
                    >
                      {(videoOptions.length
                        ? videoOptions
                        : [
                            "selfhost/video_minimax_h3_r2v_fast.json",
                            "selfhost/video_minimax_h3_r2v_turbo.json",
                            "selfhost/video_minimax_h3_r2v_lora.json",
                            "selfhost/video_minimax_h3_r2v.json",
                          ]
                      ).map((w) => (
                        <option key={w} value={w}>
                          {w}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    视频宽高比
                    <select
                      value={workflow.aspect || "9:16"}
                      onChange={(e) =>
                        setWorkflow((prev) => ({
                          ...prev,
                          aspect: e.target.value,
                        }))
                      }
                    >
                      {aspectOptions.map((a) => (
                        <option key={a} value={a}>
                          {ASPECT_LABEL[a] || a}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    图像默认工作流（可选）
                    <select
                      value={workflow.image_default_workflow || ""}
                      onChange={(e) =>
                        setWorkflow((prev) => ({
                          ...prev,
                          image_default_workflow: e.target.value || null,
                        }))
                      }
                    >
                      <option value="">（未设置）</option>
                      {imageOptions.map((w) => (
                        <option key={w} value={w}>
                          {w}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    参考图工作流
                    <select
                      value={workflow.image_reference_workflow || ""}
                      onChange={(e) =>
                        setWorkflow((prev) => ({
                          ...prev,
                          image_reference_workflow: e.target.value || null,
                        }))
                      }
                    >
                      <option value="">（未设置）</option>
                      {imageOptions.map((w) => (
                        <option key={w} value={w}>
                          {w}
                        </option>
                      ))}
                      {workflow.image_reference_workflow &&
                        !imageOptions.includes(
                          workflow.image_reference_workflow,
                        ) && (
                          <option value={workflow.image_reference_workflow}>
                            {workflow.image_reference_workflow}
                          </option>
                        )}
                    </select>
                  </label>
                  <p className="muted">
                    保存时写入 config.yaml；若已打开系列，同时写入该系列
                    series_runtime（default_workflow / aspect）。
                  </p>
                </section>
              </div>

              {error && <div className="modal-error">{error}</div>}
              {okMsg && <div className="modal-ok">{okMsg}</div>}

              <div className="sys-footer-actions">
                <button
                  type="button"
                  disabled={!!busy}
                  onClick={() => void handleSave()}
                >
                  {busy === "save" ? "保存中…" : "保存配置"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={!!busy}
                  onClick={() => void handleReset()}
                >
                  {busy === "reset" ? "重置中…" : "重置配置"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
