import { Download, HardDrive } from "lucide-react";

import { ModalSurface } from "../../components/ModalSurface";
import type { LocalWhisperProgress, LocalWhisperSetupInfo } from "../../types/yaverVoice";
import { clamp } from "../../utils/formatters";

export type LocalWhisperSetupPhase =
  | "loading"
  | "confirm"
  | "downloading"
  | "verifying"
  | "complete"
  | "error";

function formatBytes(value: number): string {
  const safeValue = Math.max(0, Number.isFinite(value) ? value : 0);
  const gigabyte = 1024 ** 3;
  const megabyte = 1024 ** 2;
  if (safeValue >= gigabyte) return `${(safeValue / gigabyte).toFixed(2)} GB`;
  return `${(safeValue / megabyte).toFixed(safeValue >= 100 * megabyte ? 0 : 1)} MB`;
}

export function LocalWhisperSetupDialog({
  phase,
  info,
  progress,
  error,
  onClose,
  onConfirm,
  onRetry
}: {
  phase: LocalWhisperSetupPhase;
  info: LocalWhisperSetupInfo | null;
  progress: LocalWhisperProgress | null;
  error: string;
  onClose: () => void;
  onConfirm: () => void;
  onRetry: () => void;
}) {
  const active = phase === "downloading" || phase === "verifying";
  const downloadedBytes = progress?.downloaded_bytes ?? 0;
  const totalBytes = progress?.total_bytes ?? info?.total_bytes ?? 0;
  const percent = phase === "complete" ? 100 : clamp(progress?.percent ?? 0, 0, 100);
  const modelDir = progress?.model_dir ?? info?.model_dir ?? "";
  const dismiss = active ? () => undefined : onClose;

  return (
    <ModalSurface
      labelledBy="local-whisper-setup-title"
      className="localSetupDialog"
      closeOnBackdrop={!active}
      onClose={dismiss}
    >
      <div className="localSetupHeading">
        <span className="localSetupIcon" aria-hidden="true">
          {active ? <Download size={20} /> : <HardDrive size={20} />}
        </span>
        <div>
          <span className="localSetupEyebrow">Local Whisper</span>
          <h3 id="local-whisper-setup-title">
            {phase === "loading"
              ? "Checking model details"
              : phase === "confirm"
                ? "Download local model?"
                : phase === "complete"
                  ? "Local model is ready"
                  : phase === "error"
                    ? "Local model setup failed"
                    : phase === "verifying"
                      ? "Verifying local model"
                      : "Downloading local model"}
          </h3>
        </div>
      </div>

      {phase === "loading" && <p className="localSetupLead">Reading model size and source without downloading files…</p>}

      {info && phase === "confirm" && (
        <>
          <p className="localSetupLead">
            The model will stay on this device. Downloading starts only after you confirm.
          </p>
          <dl className="localSetupDetails">
            <div><dt>Profile</dt><dd>{info.display_name}</dd></div>
            <div><dt>Model</dt><dd>{info.model}</dd></div>
            <div><dt>Download size</dt><dd>{formatBytes(info.total_bytes)}</dd></div>
            <div><dt>Exact size</dt><dd>{info.total_bytes.toLocaleString()} bytes</dd></div>
            <div><dt>Source</dt><dd>{info.repository}</dd></div>
          </dl>
          <div className="localSetupPath">
            <span>Source URL</span>
            <code>{info.source_url}</code>
          </div>
          <div className="localSetupPath">
            <span>Download folder</span>
            <code>{info.model_dir}</code>
          </div>
        </>
      )}

      {(active || phase === "complete") && (
        <>
          <div
            className={`progressBlock ${phase === "complete" ? "complete" : "active"}`}
            aria-label="Local model download progress"
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={Math.round(percent)}
            role="progressbar"
          >
            <div className="progressMeta">
              <span>{phase === "verifying" ? "Verifying files" : phase === "complete" ? "Complete" : "Downloading"}</span>
              <span>{Math.round(percent)}%</span>
            </div>
            <div className="progressTrack">
              <div className="progressFill" style={{ width: `${percent}%` }} />
            </div>
          </div>
          <div className="localSetupByteRow">
            <div>
              <strong>{formatBytes(downloadedBytes)} / {formatBytes(totalBytes)}</strong>
              <small>{downloadedBytes.toLocaleString()} / {totalBytes.toLocaleString()} bytes</small>
            </div>
            <span>{progress?.message ?? "Downloading local model…"}</span>
          </div>
          <div className="localSetupPath">
            <span>Source</span>
            <code>{info?.source_url ?? ""}</code>
          </div>
          <div className="localSetupPath">
            <span>Download folder</span>
            <code>{modelDir}</code>
          </div>
        </>
      )}

      {phase === "error" && (
        <p className="localSetupError" role="alert">{error || "Local model setup failed."}</p>
      )}

      <div className="localSetupActions">
        {phase === "confirm" && info && (
          <>
            <button className="secondaryButton" type="button" onClick={onClose}>Cancel</button>
            <button className="primaryButton" type="button" onClick={onConfirm}>
              Download {formatBytes(info.total_bytes)} model
            </button>
          </>
        )}
        {phase === "error" && (
          <>
            <button className="secondaryButton" type="button" onClick={onClose}>Close</button>
            <button className="primaryButton" type="button" onClick={onRetry}>Try again</button>
          </>
        )}
        {phase === "complete" && (
          <button className="primaryButton" type="button" onClick={onClose}>Done</button>
        )}
      </div>
    </ModalSurface>
  );
}
