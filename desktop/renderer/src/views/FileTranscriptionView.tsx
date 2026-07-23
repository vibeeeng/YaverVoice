import { useEffect, useRef, useState } from "react";
import { FileAudio, FolderOpen } from "lucide-react";

import { ModalSurface } from "../components/ModalSurface";
import type { FileDuration, HistoryItem, SelectedFile } from "../types/yaverVoice";
import type { ToastMessage } from "../types/ui";
import { clamp, formatAudioDuration } from "../utils/formatters";

export function FileTranscriptionView({
  onHistory,
  pushToast
}: {
  onHistory: (items: HistoryItem[]) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [file, setFile] = useState<SelectedFile | null>(null);
  const [duration, setDuration] = useState<FileDuration | null>(null);
  const [notice, setNotice] = useState("");
  const [processing, setProcessing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [progressState, setProgressState] = useState<"idle" | "active" | "complete" | "error">("idle");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const workflowSurfaceRef = useRef<HTMLDivElement | null>(null);

  const durationLabel = formatAudioDuration(duration);
  const fileModeLabel = duration?.should_split ? "Split required" : "Single pass";
  const estimatedTotalSeconds = duration?.duration_seconds && duration.duration_seconds > 0
    ? clamp(duration.duration_seconds * 0.5, 30, 300)
    : 90;

  useEffect(() => {
    return window.yaverVoice.onSidecarEvent((event) => {
      if (event.method === "file.status" && typeof event.params.message === "string") {
        setNotice(event.params.message);
        if (event.params.state === "complete" || event.params.state === "error") {
          setProcessing(false);
          setProgress(event.params.state === "complete" ? 100 : 100);
          setProgressState(event.params.state === "complete" ? "complete" : "error");
        }
      }
      if (event.method === "split.step") {
        const state = typeof event.params.state === "string" ? event.params.state : "split";
        const total = typeof event.params.total_parts === "number" ? ` (${event.params.total_parts} parts)` : "";
        const message = typeof event.params.message === "string" ? event.params.message : `Split workflow: ${state}${total}`;
        setNotice(message);
        if (event.params.state === "split_complete") {
          setProgress(20);
          setProgressState("active");
        }
        if (event.params.state === "complete" || event.params.state === "error") {
          setProcessing(false);
          setProgress(100);
          setProgressState(event.params.state === "complete" ? "complete" : "error");
        }
      }
      if (event.method === "split.progress") {
        const current = typeof event.params.current === "number" ? event.params.current : 0;
        const total = typeof event.params.total === "number" && event.params.total > 0 ? event.params.total : 0;
        setNotice(`Split transcription: ${event.params.current ?? "?"}/${event.params.total ?? "?"}`);
        if (total > 0) {
          setProgress(clamp(20 + (current / total) * 75, 20, 95));
          setProgressState("active");
        }
      }
    });
  }, []);

  useEffect(() => {
    if (!processing || duration?.should_split || startedAt === null) {
      return undefined;
    }

    const updateEstimatedProgress = () => {
      const elapsedSeconds = (Date.now() - startedAt) / 1000;
      setProgress(clamp((elapsedSeconds / estimatedTotalSeconds) * 92, 5, 92));
    };

    updateEstimatedProgress();
    const interval = window.setInterval(updateEstimatedProgress, 500);
    return () => window.clearInterval(interval);
  }, [duration?.should_split, estimatedTotalSeconds, processing, startedAt]);

  const selectFile = async () => {
    try {
      const selected = await window.yaverVoice.files.select();
      setFile(selected);
      setDuration(null);
      setProcessing(false);
      setConfirmOpen(false);
      setProgress(null);
      setProgressState("idle");
      setStartedAt(null);
      setNotice(selected ? "File selected." : "Selection cancelled.");
      if (!selected) {
        pushToast("Selection cancelled", "info");
      }
      if (selected) {
        setDuration(await window.yaverVoice.files.checkDuration(selected.token));
      }
    } catch (error) {
      setFile(null);
      setDuration(null);
      setProcessing(false);
      setConfirmOpen(false);
      setProgress(null);
      setProgressState("idle");
      setStartedAt(null);
      const text = error instanceof Error ? error.message : "File selection failed.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  const transcribe = () => {
    if (!file) {
      return;
    }
    setConfirmOpen(true);
  };

  const startTranscription = async () => {
    if (!file) {
      return;
    }
    try {
      setConfirmOpen(false);
      setProcessing(true);
      setProgress(duration?.should_split ? 5 : 0);
      setProgressState("active");
      setStartedAt(Date.now());
      setNotice(duration?.should_split ? "Split workflow starting..." : "Transcription starting...");
      const response = duration?.should_split
        ? await window.yaverVoice.split.start(file.token)
        : await window.yaverVoice.files.transcribe(file.token);
      onHistory(response.history);
      const text = response.message ?? (response.success ? "Transcription started." : "Transcription failed.");
      setNotice(text);
      if (!response.accepted) {
        setProcessing(false);
        setProgressState(response.success ? "complete" : "error");
        setProgress(response.success ? 100 : 100);
      }
    } catch (error) {
      setProcessing(false);
      setProgress(100);
      setProgressState("error");
      setNotice(error instanceof Error ? error.message : "Transcription failed.");
      pushToast(error instanceof Error ? error.message : "Transcription failed.", "error");
    }
  };

  return (
    <div className="fileWorkflow">
      <div className="fileWorkflowHeader">
        <div>
          <h3>Transcribe audio or video</h3>
        </div>
      </div>
      <div className="workflowSurface" ref={workflowSurfaceRef} tabIndex={-1}>
        <div className="fileSelectionRow">
          <button className="secondaryButton" type="button" onClick={() => void selectFile()}>
            <FolderOpen size={16} />
            Select file
          </button>
          {file && (
            <p className="fileMetadata">
              {file.name} · {file.size_mb.toFixed(2)} MB · {durationLabel} · {duration ? `${duration.provider} · ${fileModeLabel}` : "Checking duration"}
            </p>
          )}
        </div>
        <div className="workflowActions">
          <button className="primaryButton" type="button" onClick={() => void transcribe()} disabled={!file || !duration || processing}>
            <FileAudio size={16} />
            {processing ? "Processing" : duration?.should_split ? "Split and transcribe" : "Transcribe"}
          </button>
        </div>
        {progress !== null && (
          <div className={`progressBlock ${progressState}`} aria-label="File transcription progress" aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(progress)} role="progressbar">
            <div className="progressMeta">
              <span>{progressState === "error" ? "Failed" : progressState === "complete" ? "Complete" : "Processing"}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="progressTrack">
              <div className="progressFill" style={{ width: `${clamp(progress, 0, 100)}%` }} />
            </div>
          </div>
        )}
        <div className="workflowStatus" aria-live="polite">
          {notice && <p className="statusText">{notice}</p>}
        </div>
      </div>
      {confirmOpen && file && (
        <ModalSurface labelledBy="file-confirm-title" className="confirmDialog" onClose={() => setConfirmOpen(false)} returnFocusFallbackRef={workflowSurfaceRef}>
            <h3 id="file-confirm-title">Start transcription?</h3>
            <p>{file.name}</p>
            <dl>
              <div>
                <dt>Duration</dt>
                <dd>{durationLabel}</dd>
              </div>
              <div>
                <dt>Size</dt>
                <dd>{file.size_mb.toFixed(2)} MB</dd>
              </div>
              <div>
                <dt>Provider</dt>
                <dd>{duration?.provider ?? "Unknown"}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>{fileModeLabel}</dd>
              </div>
            </dl>
            <div className="buttonRow">
              <button className="secondaryButton" type="button" onClick={() => setConfirmOpen(false)}>
                Cancel
              </button>
              <button className="primaryButton" type="button" onClick={() => void startTranscription()}>
                Start transcription
              </button>
            </div>
        </ModalSurface>
      )}
    </div>
  );
}
