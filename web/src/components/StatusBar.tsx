import { useEffect, useState } from "react";
import type { StatusPayload } from "../api";

type Props = {
  status: StatusPayload | null;
};

export function StatusBar({ status }: Props) {
  const [label, setLabel] = useState("未选择系列");

  useEffect(() => {
    setLabel(status?.status_label_zh || "未选择系列");
  }, [status]);

  return (
    <div className="status-bar" title="只读状态栏">
      {label}
    </div>
  );
}
