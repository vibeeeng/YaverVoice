import { useEffect, useState } from "react";
import { Download, FolderOpen } from "lucide-react";

import type { FfmpegStatus, OutputFormat, SelectedFile } from "../types/yaverVoice";
import type { ToastMessage } from "../types/ui";

export function ConverterView({ pushToast }: { pushToast: (message: string, type?: ToastMessage["type"]) => void }) {
  const [file, setFile] = useState<SelectedFile | null>(null);
  const [formats, setFormats] = useState<OutputFormat[]>([]);
  const [status, setStatus] = useState<FfmpegStatus | null>(null);
  const [format, setFormat] = useState("mp3");
  const [notice, setNotice] = useState("");
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    void Promise.all([window.yaverVoice.converter.status(), window.yaverVoice.converter.outputFormats()]).then(([nextStatus, nextFormats]) => {
      setStatus(nextStatus);
      setFormats(nextFormats);
      if (nextFormats[0]) {
        setFormat(nextFormats[0].key);
      }
    });
  }, []);

  useEffect(() => {
    return window.yaverVoice.onSidecarEvent((event) => {
      if (event.method !== "converter.status") {
        return;
      }
      if (typeof event.params.message === "string") {
        setNotice(event.params.message);
      }
      if (event.params.state === "complete" || event.params.state === "error") {
        setProcessing(false);
      }
    });
  }, []);

  const selectFile = async () => {
    try {
      const selected = await window.yaverVoice.converter.select();
      setFile(selected);
      setProcessing(false);
      setNotice(selected ? selected.name : "Selection cancelled.");
      if (!selected) {
        pushToast("Selection cancelled", "info");
      }
    } catch (error) {
      setFile(null);
      setProcessing(false);
      const text = error instanceof Error ? error.message : "File selection failed.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  const convert = async () => {
    if (!file) {
      return;
    }
    try {
      setProcessing(true);
      setNotice("Conversion starting...");
      const response = await window.yaverVoice.converter.convert(file.token, format, `${file.name.replace(/\.[^.]+$/, "")}.${format}`);
      const text = response.message ?? (response.success ? "Conversion complete." : "Conversion failed.");
      setNotice(text);
      if (!response.accepted) {
        setProcessing(false);
        pushToast(text, response.success ? "success" : "error");
      }
    } catch (error) {
      setProcessing(false);
      const text = error instanceof Error ? error.message : "Conversion failed.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  return (
    <div className="fileWorkflow">
      <div className="fileWorkflowHeader">
        <div>
          <span className="eyebrow">CONVERSION</span>
          <h3>Convert media</h3>
        </div>
        <span className="contextStatus">FFmpeg: {status?.installed ? "Ready" : "Not available"}</span>
      </div>
      <div className="fileSelectionRow">
        <button className="secondaryButton" type="button" onClick={() => void selectFile()}>
          <FolderOpen size={16} />
          Select file
        </button>
        {file && <p className="fileMetadata">{file.name}</p>}
      </div>
      <div className="fieldGrid">
        <label>
          Output format
          <select value={format} onChange={(event) => setFormat(event.target.value)} disabled={formats.length === 0}>
            {formats.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}
          </select>
        </label>
      </div>
      <div className="workflowActions">
        <button className="primaryButton" type="button" onClick={() => void convert()} disabled={!file || !status?.installed || processing}>
          <Download size={16} />
          {processing ? "Converting" : "Convert"}
        </button>
      </div>
      <div className="workflowStatus" aria-live="polite">
        {notice && <p className="statusText">{notice}</p>}
      </div>
    </div>
  );
}
