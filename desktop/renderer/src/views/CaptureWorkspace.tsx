import type { HistoryItem, RecordingStatus, Settings } from "../types/yaverVoice";
import type { CaptureMode, ToastMessage } from "../types/ui";
import { QuickDictationView } from "./QuickDictationView";
import { RecordView } from "./RecordView";

export function CaptureWorkspace({
  mode,
  onModeChange,
  status,
  onStatus,
  settings,
  history,
  onOpenLibrary,
  pushToast
}: {
  mode: CaptureMode;
  onModeChange: (mode: CaptureMode) => void;
  status: RecordingStatus;
  onStatus: (status: RecordingStatus) => void;
  settings: Settings | null;
  history: HistoryItem[];
  onOpenLibrary: () => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const latest = history[0];
  return (
    <section className="workspace captureWorkspace" aria-labelledby="capture-title">
      <div className="workspaceHeader">
        <div><span className="eyebrow">VOICE INPUT</span><h2 id="capture-title">Capture</h2></div>
        <span className="contextStatus">{settings?.transcription_provider === "local" ? "Local Whisper" : "Groq Cloud"}</span>
      </div>
      <div className="segmentedControl" role="tablist" aria-label="Capture mode">
        <button aria-controls="capture-quick-panel" aria-selected={mode === "quick"} className={mode === "quick" ? "active" : ""} onClick={() => onModeChange("quick")} role="tab" type="button">Quick Dictation</button>
        <button aria-controls="capture-record-panel" aria-selected={mode === "record"} className={mode === "record" ? "active" : ""} onClick={() => onModeChange("record")} role="tab" type="button">Record</button>
      </div>
      <div hidden={mode !== "quick"} id="capture-quick-panel" role="tabpanel"><QuickDictationView status={status} onStatus={onStatus} pushToast={pushToast} /></div>
      <div hidden={mode !== "record"} id="capture-record-panel" role="tabpanel"><RecordView status={status} onStatus={onStatus} settings={settings} pushToast={pushToast} /></div>
      {latest && (
        <aside className="latestTranscript" aria-label="Last transcript">
          <div><span className="eyebrow">LAST TRANSCRIPT</span><p>{latest.text}</p></div>
          <div className="tertiaryActions">
            <button type="button" onClick={() => void window.yaverVoice.clipboard.copy(latest.text).then(() => pushToast("Copied to clipboard", "success"))}>Copy</button>
            <button type="button" onClick={onOpenLibrary}>Open in Library</button>
          </div>
        </aside>
      )}
    </section>
  );
}
