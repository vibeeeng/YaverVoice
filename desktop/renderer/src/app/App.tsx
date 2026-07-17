import React, { useCallback, useEffect, useState } from "react";
import { RefreshCcw } from "lucide-react";
import type {
  HistoryItem,
  RecordingStatus,
  Settings,
  SidecarLogEntry
} from "../types/yaverVoice";
import { ToastViewport } from "../components/ToastViewport";
import type {
  CaptureMode,
  FilesMode,
  GlobalProgressEntry,
  ToastMessage,
  WorkspaceId
} from "../types/ui";
import { clamp } from "../utils/formatters";
import { CaptureWorkspace } from "../views/CaptureWorkspace";
import { FilesWorkspace } from "../views/FilesWorkspace";
import { HistoryView } from "../views/HistoryView";
import { SettingsView } from "../views/settings/SettingsView";
import logoUrl from "../../../../logo/logo2.png";
import { workspaces } from "./navigation";
import { handleSidecarEvent } from "./sidecarEvents";

export default function App() {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("capture");
  const [captureMode, setCaptureMode] = useState<CaptureMode>("quick");
  const [filesMode, setFilesMode] = useState<FilesMode>("transcribe");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [logs, setLogs] = useState<SidecarLogEntry[]>([]);
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus>({ recording: false, transcribing: false, mode: "standard" });
  const [status, setStatus] = useState<"connecting" | "ready" | "error">("connecting");
  const [message, setMessage] = useState<string>("Starting YaverVoice sidecar");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [historyEditUnlocked, setHistoryEditUnlocked] = useState(false);
  const [globalProgress, setGlobalProgress] = useState<GlobalProgressEntry[]>([]);

  const pushToast = useCallback((nextMessage: string, type: ToastMessage["type"] = "info") => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    setToasts((current) => [{ id, message: nextMessage, type }, ...current].slice(0, 4));
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 4200);
  }, []);

  const updateGlobalProgress = useCallback(
    (entry: GlobalProgressEntry) => {
      setGlobalProgress((current) => {
        const filtered = current.filter((e) => e.source !== entry.source);
        return [...filtered, entry];
      });
    },
    []
  );

  const clearGlobalProgress = useCallback(
    (source: GlobalProgressEntry["source"]) => {
      setGlobalProgress((current) => current.filter((e) => e.source !== source));
    },
    []
  );

  const refresh = async () => {
    try {
      await window.yaverVoice.ping();
      const [nextSettings, nextHistory] = await Promise.all([
        window.yaverVoice.settings.get(),
        window.yaverVoice.history.list()
      ]);
      setSettings(nextSettings);
      setHistory(nextHistory);
      setStatus("ready");
      setMessage("Sidecar connected");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Sidecar unavailable");
    }
  };

  useEffect(() => {
    void refresh();
    const removeLogListener = window.yaverVoice.onSidecarLog((entry) => {
      setLogs((current) => [entry, ...current].slice(0, 20));
    });
    const removeEventListener = window.yaverVoice.onSidecarEvent((event) => {
      handleSidecarEvent(event, setSettings, setHistory, setRecordingStatus, pushToast, setMessage, updateGlobalProgress, clearGlobalProgress);
    });
    return () => {
      removeLogListener();
      removeEventListener();
    };
  }, [pushToast, updateGlobalProgress, clearGlobalProgress]);

  const openProgressSource = (source: GlobalProgressEntry["source"]) => {
    setActiveWorkspace("files");
    setFilesMode(source === "docs" ? "notes" : source === "converter" ? "convert" : "transcribe");
  };

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <img className="brandLogo" src={logoUrl} alt="" aria-hidden="true" />
          </div>
          <div>
            <strong>YaverVoice</strong>
          </div>
        </div>
        <nav className="navList" aria-label="Main navigation">
          {workspaces.map((workspace) => {
            const Icon = workspace.icon;
            return (
              <button
                aria-current={activeWorkspace === workspace.id ? "page" : undefined}
                className={activeWorkspace === workspace.id ? "navItem active" : "navItem"}
                key={workspace.id}
                onClick={() => setActiveWorkspace(workspace.id)}
                type="button"
              >
                <Icon size={15} />
                <span>{workspace.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="mainPane">
        <header className="topbar">
          <div>
            <h1>{workspaces.find((workspace) => workspace.id === activeWorkspace)?.label}</h1>
          </div>
          <div className="topbarActions">
            <span className={`connectionStatus ${status}`} role="status">
              <span className="connectionDot" aria-hidden="true" />
              {message}
            </span>
            <button className="iconButton" onClick={() => void refresh()} title="Refresh app data" type="button">
              <RefreshCcw size={17} />
            </button>
          </div>
        </header>

        {globalProgress.filter((e) => e.state === "active").length > 0 && (
          <section className="globalProgressStrip" aria-label="Background progress">
            {globalProgress
              .filter((e) => e.state === "active")
              .map((entry) => {
                return (
                  <button
                    key={entry.source}
                    className="globalProgressItem"
                    type="button"
                    onClick={() => openProgressSource(entry.source)}
                  >
                    <span className="globalProgressLabel">{entry.label}</span>
                    <span className="globalProgressPercent">{Math.round(entry.percent)}%</span>
                    <div className="globalProgressTrack" aria-label={`${entry.label} progress`} aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(clamp(entry.percent, 0, 100))} role="progressbar">
                      <div className="globalProgressFill" style={{ width: `${clamp(entry.percent, 0, 100)}%` }} />
                    </div>
                  </button>
                );
              })}
          </section>
        )}

        <section className="contentBand">
          <div hidden={activeWorkspace !== "capture"}>
            <CaptureWorkspace
              mode={captureMode}
              onModeChange={setCaptureMode}
              status={recordingStatus}
              onStatus={setRecordingStatus}
              settings={settings}
              history={history}
              onOpenLibrary={() => setActiveWorkspace("library")}
              pushToast={pushToast}
            />
          </div>
          <div hidden={activeWorkspace !== "files"}>
            <FilesWorkspace
              mode={filesMode}
              onModeChange={setFilesMode}
              settings={settings}
              onHistory={setHistory}
              pushToast={pushToast}
            />
          </div>
          <div hidden={activeWorkspace !== "library"}>
            <HistoryView
              editUnlocked={historyEditUnlocked}
              onEditUnlocked={setHistoryEditUnlocked}
              history={history}
              onHistory={setHistory}
              onOpenCapture={() => setActiveWorkspace("capture")}
              onOpenFiles={() => setActiveWorkspace("files")}
              pushToast={pushToast}
            />
          </div>
          {settings && (
            <div hidden={activeWorkspace !== "settings"}>
              <SettingsView settings={settings} onSettings={setSettings} pushToast={pushToast} />
            </div>
          )}
        </section>

        <ToastViewport toasts={toasts} />

        {logs.length > 0 && (
          <section className="logStrip" aria-label="Sidecar logs">
            {logs.slice(0, 3).map((entry, index) => (
              <span key={`${entry.message}-${index}`} className={entry.level}>
                {entry.message}
              </span>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
