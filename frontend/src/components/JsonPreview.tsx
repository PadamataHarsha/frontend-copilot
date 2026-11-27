import { useState } from "react";
import type { WireframeResponse } from "../types/wireframe";
interface JsonPreviewProps { data: WireframeResponse; }

export function JsonPreview({ data }: JsonPreviewProps) {
  const [copyLabel, setCopyLabel] = useState("Copy JSON");
  const json = JSON.stringify(data, null, 2);
  const copyJson = async () => {
    try { await navigator.clipboard.writeText(json); setCopyLabel("Copied"); }
    catch { setCopyLabel("Copy unavailable"); }
    window.setTimeout(() => setCopyLabel("Copy JSON"), 1800);
  };
  return <details className="json-preview"><summary>Structured response <span>JSON</span></summary><div className="json-content"><button className="copy-json" type="button" onClick={copyJson}>{copyLabel}</button><pre><code>{json}</code></pre></div></details>;
}