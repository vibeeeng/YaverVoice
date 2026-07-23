import type { HistoryItem, Settings } from "../types/yaverVoice";
import type { FilesMode, ToastMessage } from "../types/ui";
import { ProcessingContextBadge, type ProcessingContextMode } from "../components/ProcessingContextBadge";
import { ConverterView } from "./ConverterView";
import { FileTranscriptionView } from "./FileTranscriptionView";
import { DocsView } from "./docs/DocsView";

const modes: Array<{ id: FilesMode; label: string }> = [
  { id: "transcribe", label: "Transcribe" },
  { id: "notes", label: "Create Notes" },
  { id: "convert", label: "Convert" }
];

const processingContexts: Record<FilesMode, Array<{ mode: ProcessingContextMode; label: string }>> = {
  transcribe: [{ mode: "transcription", label: "Transcription" }],
  notes: [
    { mode: "transcription", label: "Transcription" },
    { mode: "notes-generation", label: "Notes generation" }
  ],
  convert: [{ mode: "media-conversion", label: "Media conversion" }]
};

export function FilesWorkspace({ mode, onModeChange, settings, onHistory, pushToast }: {
  mode: FilesMode;
  onModeChange: (mode: FilesMode) => void;
  settings: Settings | null;
  onHistory: (items: HistoryItem[]) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  return (
    <section className="workspace filesWorkspace" aria-labelledby="files-title">
      <div className="workspaceHeader">
        <h2 id="files-title">Files</h2>
        <div className="processingContextGroup">
          {processingContexts[mode].map((context) => (
            <ProcessingContextBadge key={context.mode} settings={settings} mode={context.mode} label={context.label} />
          ))}
        </div>
      </div>
      <div className="workspaceTabs" role="tablist" aria-label="File workflow">
        {modes.map((item) => <button aria-controls={`files-${item.id}-panel`} aria-selected={mode === item.id} className={mode === item.id ? "active" : ""} key={item.id} onClick={() => onModeChange(item.id)} role="tab" type="button">{item.label}</button>)}
      </div>
      <div hidden={mode !== "transcribe"} id="files-transcribe-panel" role="tabpanel"><FileTranscriptionView onHistory={onHistory} pushToast={pushToast} /></div>
      <div hidden={mode !== "notes"} id="files-notes-panel" role="tabpanel"><DocsView settings={settings} onHistory={onHistory} pushToast={pushToast} /></div>
      <div hidden={mode !== "convert"} id="files-convert-panel" role="tabpanel"><ConverterView pushToast={pushToast} /></div>
    </section>
  );
}
