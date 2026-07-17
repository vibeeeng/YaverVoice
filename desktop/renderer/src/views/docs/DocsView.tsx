import { useCallback, useEffect, useState } from "react";
import { FileText, FolderOpen } from "lucide-react";

import type {
  DocsDetailProfile,
  DocsDirectorySelection,
  DocsModelProfile,
  FileDuration,
  HistoryItem,
  SelectedFile,
  Settings
} from "../../types/yaverVoice";
import type { DocsOutputLanguage, ToastMessage } from "../../types/ui";
import { DocsBrowserPanel } from "./DocsBrowserPanel";
import { DocsOptionsPanel } from "./DocsOptionsPanel";
import { DocsProgressPanel } from "./DocsProgressPanel";
import {
  clamp,
  docsOutputLanguageFromSettings,
  estimateDocsCallsFromDuration,
  formatAudioDuration,
  formatDocsLogEntry,
  formatDocsPhaseLabel,
  formatDocsProgressEntry
} from "../../utils/formatters";

const docsOutputLanguages: Array<{ id: DocsOutputLanguage; label: string }> = [
  { id: "same", label: "Same as transcript" },
  { id: "tr", label: "Turkish" },
  { id: "en", label: "English" },
  { id: "de", label: "German" },
  { id: "fr", label: "French" },
  { id: "es", label: "Spanish" },
  { id: "it", label: "Italian" }
];
export function DocsView({
  settings,
  onHistory,
  pushToast
}: {
  settings: Settings | null;
  onHistory: (items: HistoryItem[]) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [file, setFile] = useState<SelectedFile | null>(null);
  const [duration, setDuration] = useState<FileDuration | null>(null);
  const [models, setModels] = useState<DocsModelProfile[]>([]);
  const [details, setDetails] = useState<DocsDetailProfile[]>([]);
  const [selectedModel, setSelectedModel] = useState("meta-llama/llama-4-scout-17b-16e-instruct");
  const [selectedDetail, setSelectedDetail] = useState("standard");
  const [selectedOutputLanguage, setSelectedOutputLanguage] = useState<DocsOutputLanguage>(() => docsOutputLanguageFromSettings(settings?.language));
  const [outputLanguageTouched, setOutputLanguageTouched] = useState(false);
  const [docsLog, setDocsLog] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [progressState, setProgressState] = useState<"idle" | "active" | "complete" | "error">("idle");
  const [progressPhase, setProgressPhase] = useState("idle");
  const [progressLabel, setProgressLabel] = useState("Processing");
  const [activeRecordingId, setActiveRecordingId] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [modelInfoOpen, setModelInfoOpen] = useState(false);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [docsOutputOpen, setDocsOutputOpen] = useState(false);
  const [docsDir, setDocsDir] = useState<string | null>(null);
  const [docsDirToken, setDocsDirToken] = useState<string | null>(null);
  const [docsFiles, setDocsFiles] = useState<Array<{ name: string; path: string }>>([]);
  const [docsDirLoading, setDocsDirLoading] = useState(false);

  const durationLabel = formatAudioDuration(duration);
  const fileModeLabel = duration?.should_split ? "Split + Docs" : "Single pass + Docs";
  const activeModel = models.find((model) => model.id === selectedModel);
  const activeDetail = details.find((detail) => detail.id === selectedDetail);
  const activeOutputLanguage = docsOutputLanguages.find((language) => language.id === selectedOutputLanguage) ?? docsOutputLanguages[0];
  const estimatedDocsCalls = file && activeModel
    ? estimateDocsCallsFromDuration(duration, activeModel)
    : null;
  const estimatedTotalSeconds = duration?.duration_seconds && duration.duration_seconds > 0
    ? clamp(duration.duration_seconds * 0.65, 40, 360)
    : 110;

  useEffect(() => {
    void Promise.all([window.yaverVoice.docs.models(), window.yaverVoice.docs.details()]).then(([profiles, detailProfiles]) => {
      setModels(profiles);
      setDetails(detailProfiles);
      if (profiles[0]) {
        setSelectedModel((current) => profiles.some((profile) => profile.id === current) ? current : profiles[0].id);
      }
      if (detailProfiles[0]) {
        setSelectedDetail((current) => detailProfiles.some((profile) => profile.id === current) ? current : detailProfiles[0].id);
      }
    }).catch((error) => {
      const text = error instanceof Error ? error.message : "Docs models could not be loaded.";
      setNotice(text);
      pushToast(text, "error");
    });
  }, [pushToast]);

  useEffect(() => {
    if (!outputLanguageTouched) {
      setSelectedOutputLanguage(docsOutputLanguageFromSettings(settings?.language));
    }
  }, [outputLanguageTouched, settings?.language]);

  const loadDocsDir = useCallback(async (selection: DocsDirectorySelection) => {
    setDocsDir(selection.path);
    setDocsDirToken(selection.token);
    setDocsDirLoading(true);
    try {
      const files = await window.yaverVoice.docs.listDirectory(selection.token);
      setDocsFiles(files);
    } catch {
      setDocsFiles([]);
    } finally {
      setDocsDirLoading(false);
    }
  }, []);

  const selectDocsDir = useCallback(async () => {
    try {
      const selection = await window.yaverVoice.docs.selectDirectory();
      if (selection) {
        await loadDocsDir(selection);
      }
    } catch {
      // cancelled
    }
  }, [loadDocsDir]);

  const openPreview = useCallback(async (filePath: string) => {
    setPreviewPath(filePath);
    setPreviewContent(null);
    setPreviewLoading(true);
    setPreviewOpen(true);
    try {
      const result = await window.yaverVoice.docs.readFile(filePath, docsDirToken ?? undefined);
      setPreviewContent(result.content);
    } catch {
      setPreviewContent(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [docsDirToken]);

  useEffect(() => {
    if (!modelInfoOpen) {
      return undefined;
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setModelInfoOpen(false);
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".docsInfoToggle")) {
        setModelInfoOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("click", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("click", handleClickOutside);
    };
  }, [modelInfoOpen]);

  useEffect(() => {
    return window.yaverVoice.onSidecarEvent((event) => {
      const params = event.params as Record<string, unknown>;
      const eventRecordingId = typeof params["recording_id"] === "string" ? params["recording_id"] : null;
      if (activeRecordingId && eventRecordingId && eventRecordingId !== activeRecordingId) {
        return;
      }
      if (event.method === "docs.status" && typeof event.params.message === "string") {
        setNotice(event.params.message);
        setDocsLog((current) => [
          formatDocsLogEntry(event.params.message as string, event.params),
          ...current
        ].slice(0, 6));
        const percent = typeof event.params.percent === "number" ? event.params.percent : null;
        const phase = typeof event.params.phase === "string" ? event.params.phase : null;
        if (phase) {
          setProgressPhase(phase);
          setProgressLabel(formatDocsPhaseLabel(phase));
        }
        if (percent !== null) {
          setProgress(clamp(percent, 0, 100));
          setProgressState("active");
        }
        if (event.params.state === "processing") {
          setProgress(percent ?? 4);
          setProgressState("active");
        }
        if (event.params.state === "splitting") {
          setProgress(percent ?? 10);
          setProgressState("active");
        }
        if (event.params.state === "split_complete") {
          setProgress(percent ?? 18);
          setProgressState("active");
        }
        if (event.params.state === "summarizing") {
          setProgress(percent ?? 92);
          setProgressState("active");
        }
        if (event.params.state === "complete" || event.params.state === "error") {
          setProcessing(false);
          setProgress(100);
          setProgressState(event.params.state === "complete" ? "complete" : "error");
          setProgressPhase(event.params.state === "complete" ? "complete" : "error");
          setProgressLabel(event.params.state === "complete" ? "Complete" : "Failed");
          if (event.params.state === "complete") {
            const dp = typeof params["display_path"] === "string" ? params["display_path"] as string : null;
            if (dp) {
              setPreviewPath(dp);
              setPreviewLoading(true);
              setPreviewOpen(true);
              window.yaverVoice.docs.readFile(dp)
                .then((result) => {
                  setPreviewContent(result.content);
                })
                .catch(() => {
                  setPreviewContent(null);
                })
                .finally(() => setPreviewLoading(false));
              if (docsDir && docsDirToken) {
                void loadDocsDir({ token: docsDirToken, path: docsDir });
              }
            }
          }
        }
      }
      if (event.method === "docs.progress") {
        const current = typeof event.params.current === "number" ? event.params.current : 0;
        const total = typeof event.params.total === "number" && event.params.total > 0 ? event.params.total : 0;
        const message = typeof event.params.message === "string"
          ? event.params.message
          : `Docs progress: ${event.params.current ?? "?"}/${event.params.total ?? "?"}`;
        const percent = typeof event.params.percent === "number" ? event.params.percent : null;
        const phase = typeof event.params.phase === "string" ? event.params.phase : "processing";
        setProgressPhase(phase);
        setProgressLabel(formatDocsPhaseLabel(phase));
        setNotice(message);
        setDocsLog((current) => [
          formatDocsProgressEntry(message, event.params),
          ...current
        ].slice(0, 6));
        if (total > 0) {
          setProgress(percent !== null ? clamp(percent, 0, 100) : clamp(18 + (current / total) * 68, 18, 88));
          setProgressState("active");
        }
      }
    });
  }, [activeRecordingId, docsDir, docsDirToken, loadDocsDir]);

  useEffect(() => {
    if (!processing || duration?.should_split || startedAt === null || progressPhase !== "transcribing") {
      return undefined;
    }
    const updateEstimatedProgress = () => {
      const elapsedSeconds = (Date.now() - startedAt) / 1000;
      setProgress(clamp((elapsedSeconds / estimatedTotalSeconds) * 86, 6, 86));
    };
    updateEstimatedProgress();
    const interval = window.setInterval(updateEstimatedProgress, 500);
    return () => window.clearInterval(interval);
  }, [duration?.should_split, estimatedTotalSeconds, processing, progressPhase, startedAt]);

  const selectFile = async () => {
    try {
      const selected = await window.yaverVoice.docs.select();
      setFile(selected);
      setDuration(null);
      setProcessing(false);
      setProgress(null);
      setProgressState("idle");
      setProgressPhase("idle");
      setProgressLabel("Processing");
      setActiveRecordingId(null);
      setStartedAt(null);
      setDocsLog([]);
      setPreviewPath(null);
      setPreviewContent(null);
      setPreviewOpen(false);
      setNotice(selected ? "File selected." : "Selection cancelled.");
      if (!selected) {
        pushToast("Selection cancelled", "info");
        return;
      }
      setDuration(await window.yaverVoice.docs.checkDuration(selected.token));
    } catch (error) {
      setFile(null);
      setDuration(null);
      setProcessing(false);
      setProgress(null);
      setProgressState("idle");
      setProgressPhase("idle");
      setProgressLabel("Processing");
      setActiveRecordingId(null);
      setStartedAt(null);
      setDocsLog([]);
      setPreviewPath(null);
      setPreviewContent(null);
      setPreviewOpen(false);
      const text = error instanceof Error ? error.message : "Docs file selection failed.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  const createDocs = async () => {
    if (!file) {
      return;
    }
    try {
      const preflight = await window.yaverVoice.docs.preflight(file.token, selectedModel, selectedDetail, selectedOutputLanguage);
      if (!preflight.ready) {
        const text = preflight.blockers[0] ?? "Docs workflow is not ready.";
        setNotice(text);
        setDocsLog((current) => [text, ...current].slice(0, 6));
        pushToast(text, "error");
        return;
      }
      if (preflight.warnings.length > 0) {
        setDocsLog((current) => [...preflight.warnings, ...current].slice(0, 6));
      }
      setProcessing(true);
      setProgress(duration?.should_split ? 5 : 0);
      setProgressState("active");
      setProgressPhase("transcribing");
      setProgressLabel(duration?.should_split ? "Splitting" : "Transcribing");
      setStartedAt(Date.now());
      setNotice("Choose where to save the Markdown document.");
      const baseName = file.name.replace(/\.[^.]+$/, "") || "docs";
      const response = await window.yaverVoice.docs.createMarkdown(file.token, `${baseName}_docs.md`, selectedModel, selectedDetail, selectedOutputLanguage);
      if (response.cancelled) {
        setProcessing(false);
        setProgress(null);
        setProgressState("idle");
        setProgressPhase("idle");
        setProgressLabel("Processing");
        setNotice("Save cancelled.");
        pushToast("Save cancelled", "info");
        return;
      }
      if (response.history) {
        onHistory(response.history);
      }
      if (response.id) {
        setActiveRecordingId(response.id);
      }
      setNotice(response.message ?? "Docs workflow started.");
      setDocsLog((current) => [
        `${response.model_label ?? activeModel?.label ?? "Docs model"} · ${response.detail_label ?? activeDetail?.label ?? "Detail"} · ${response.output_language_label ?? activeOutputLanguage.label}`,
        ...current
      ].slice(0, 6));
      if (!response.accepted) {
        setProcessing(false);
        setProgress(response.success ? 100 : 100);
        setProgressState(response.success ? "complete" : "error");
        setProgressPhase(response.success ? "complete" : "error");
        setProgressLabel(response.success ? "Complete" : "Failed");
      }
    } catch (error) {
      setProcessing(false);
      setProgress(100);
      setProgressState("error");
      setProgressPhase("error");
      setProgressLabel("Failed");
      const text = error instanceof Error ? error.message : "Docs workflow failed.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  return (
    <div className="fileWorkflow docsWorkflow">
      <DocsProgressPanel
        activeModel={activeModel}
        activeDetail={activeDetail}
        outputLanguageLabel={activeOutputLanguage.label}
        estimatedDocsCalls={estimatedDocsCalls}
        modelInfoOpen={modelInfoOpen}
        onToggleModelInfo={() => setModelInfoOpen((value) => !value)}
        file={file}
        duration={duration}
        durationLabel={durationLabel}
        fileModeLabel={fileModeLabel}
        progress={progress}
        progressState={progressState}
        progressLabel={progressLabel}
        docsLog={docsLog}
        notice={notice}
        docsOutputOpen={docsOutputOpen}
        onToggleDocsOutput={() => setDocsOutputOpen((value) => !value)}
      >
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
        <DocsOptionsPanel
          models={models}
          details={details}
          outputLanguages={docsOutputLanguages}
          selectedModel={selectedModel}
          selectedDetail={selectedDetail}
          selectedOutputLanguage={selectedOutputLanguage}
          processing={processing}
          onModelChange={setSelectedModel}
          onDetailChange={setSelectedDetail}
          onOutputLanguageChange={(language) => {
            setOutputLanguageTouched(true);
            setSelectedOutputLanguage(language);
          }}
        />
        <div className="workflowActions">
          <button className="primaryButton" type="button" onClick={() => void createDocs()} disabled={!file || !duration || processing || !activeModel || !activeDetail || !activeOutputLanguage}>
            <FileText size={16} />
            {processing ? "Creating" : "Create Markdown"}
          </button>
        </div>
      </DocsProgressPanel>
      <DocsBrowserPanel
        directory={docsDir}
        directoryToken={docsDirToken}
        directoryLoading={docsDirLoading}
        files={docsFiles}
        previewPath={previewPath}
        previewContent={previewContent}
        previewOpen={previewOpen}
        previewLoading={previewLoading}
        onSelectDirectory={() => void selectDocsDir()}
        onRefreshDirectory={() => {
          if (docsDir && docsDirToken) {
            void loadDocsDir({ token: docsDirToken, path: docsDir });
          }
        }}
        onOpenPreview={(path) => void openPreview(path)}
        onClosePreview={() => setPreviewOpen(false)}
      />
      <div className="workflowStatus" aria-live="polite">
        {progressState !== "complete" && progressState !== "error" && notice && <p className="statusText">{notice}</p>}
      </div>
    </div>
  );
}
