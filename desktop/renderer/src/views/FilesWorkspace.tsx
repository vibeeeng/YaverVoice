import type { HistoryItem, Settings } from "../types/yaverVoice";
import type { FilesMode, ToastMessage } from "../types/ui";
import { ConverterView } from "./ConverterView";
import { FileTranscriptionView } from "./FileTranscriptionView";
import { DocsView } from "./docs/DocsView";

const modes: Array<{ id: FilesMode; label: string }> = [
  { id: "transcribe", label: "Transcribe" },
  { id: "notes", label: "Create Notes" },
  { id: "convert", label: "Convert" }
];

export function FilesWorkspace({ mode, onModeChange, settings, onHistory, pushToast }: {
  mode: FilesMode;
  onModeChange: (mode: FilesMode) => void;
  settings: Settings | null;
  onHistory: (items: HistoryItem[]) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  return (
    <section className="workspace filesWorkspace" aria-labelledby="files-title">
      <div className="workspaceHeader"><div><span className="eyebrow">MEDIA WORKFLOWS</span><h2 id="files-title">Files</h2></div></div>
      <div className="workspaceTabs" role="tablist" aria-label="File workflow">
        {modes.map((item) => <button aria-controls={`files-${item.id}-panel`} aria-selected={mode === item.id} className={mode === item.id ? "active" : ""} key={item.id} onClick={() => onModeChange(item.id)} role="tab" type="button">{item.label}</button>)}
      </div>
      <div hidden={mode !== "transcribe"} id="files-transcribe-panel" role="tabpanel"><FileTranscriptionView onHistory={onHistory} pushToast={pushToast} /></div>
      <div hidden={mode !== "notes"} id="files-notes-panel" role="tabpanel"><DocsView settings={settings} onHistory={onHistory} pushToast={pushToast} /></div>
      <div hidden={mode !== "convert"} id="files-convert-panel" role="tabpanel"><ConverterView pushToast={pushToast} /></div>
    </section>
  );
}
