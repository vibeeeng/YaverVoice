import type { ReactNode } from "react";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

import type { DocsDetailProfile, DocsModelProfile, FileDuration, SelectedFile } from "../../types/yaverVoice";
import { clamp } from "../../utils/formatters";

export type DocsProgressState = "idle" | "active" | "complete" | "error";

export function DocsProgressPanel({
  children,
  activeModel,
  activeDetail,
  outputLanguageLabel,
  estimatedDocsCalls,
  modelInfoOpen,
  onToggleModelInfo,
  file,
  duration,
  durationLabel,
  fileModeLabel,
  progress,
  progressState,
  progressLabel,
  docsLog,
  notice,
  docsOutputOpen,
  onToggleDocsOutput
}: {
  children: ReactNode;
  activeModel?: DocsModelProfile;
  activeDetail?: DocsDetailProfile;
  outputLanguageLabel: string;
  estimatedDocsCalls: number | null;
  modelInfoOpen: boolean;
  onToggleModelInfo: () => void;
  file: SelectedFile | null;
  duration: FileDuration | null;
  durationLabel: string;
  fileModeLabel: string;
  progress: number | null;
  progressState: DocsProgressState;
  progressLabel: string;
  docsLog: string[];
  notice: string;
  docsOutputOpen: boolean;
  onToggleDocsOutput: () => void;
}) {
  return (
    <>
      <div className="fileWorkflowHeader">
        <div>
          <h3>Create notes</h3>
        </div>
        {activeModel && (
          <div className="docsInfoToggle">
            <button
              className="iconButton"
              type="button"
              onClick={onToggleModelInfo}
              title="Model info"
            >
              <Info size={15} />
            </button>
            {modelInfoOpen && (
              <div className="docsInfoPopover">
                <strong>{activeModel.tpm} TPM / {activeModel.tpd} TPD</strong>
                <p>{activeModel.note}</p>
                {activeDetail && <p>{activeDetail.note}</p>}
                <p>Output: {outputLanguageLabel}</p>
                {estimatedDocsCalls !== null && <p>Estimated Docs LLM calls: {estimatedDocsCalls}</p>}
              </div>
            )}
          </div>
        )}
      </div>
      <div className="workflowSurface docsStudioSurface">
        {children}
        {progress !== null && (
          <div className={`progressBlock ${progressState}`} aria-label="Docs progress" aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(progress)} role="progressbar">
            <div className="progressMeta">
              <span>{progressState === "error" ? "Failed" : progressState === "complete" ? "Complete" : progressLabel}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="progressTrack">
              <div className="progressFill" style={{ width: `${clamp(progress, 0, 100)}%` }} />
            </div>
          </div>
        )}
        {progressState !== "complete" && progressState !== "error" && (
          <div className="docsFormatPreview" aria-label="Markdown sections">
            <span>Markdown</span>
            <strong>Summary · Topics · Notes · Decisions · Actions · Questions</strong>
          </div>
        )}
        {progressState !== "complete" && progressState !== "error" && docsLog.length > 0 && (
          <div className="docsLog" aria-label="Docs log">
            {docsLog.map((entry, index) => (
              <span key={`${entry}-${index}`}>{entry}</span>
            ))}
          </div>
        )}
        {(progressState === "complete" || progressState === "error") && (
          <div className="docsResultBlock">
            <button
              className="docsResultToggle"
              type="button"
              onClick={onToggleDocsOutput}
            >
              <span>{docsLog[0] ?? notice ?? (progressState === "complete" ? "Complete" : "Failed")}</span>
              {docsOutputOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {docsOutputOpen && (
              <div className="docsResultDetail">
                {notice && <p className="statusText">{notice}</p>}
                {docsLog.length > 1 && (
                  <div className="docsLog">
                    {docsLog.slice(1).map((entry, index) => (
                      <span key={`${entry}-${index}`}>{entry}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
