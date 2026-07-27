import { contextBridge, ipcRenderer } from "electron";

type SidecarLogEntry = {
  level: "debug" | "error";
  message: string;
};

type SidecarEvent = {
  method: string;
  params: Record<string, unknown>;
};

const invoke = <T>(method: string, params?: Record<string, unknown>): Promise<T> => {
  return ipcRenderer.invoke("yavervoice:invoke", method, params ?? {}) as Promise<T>;
};

const api = {
  ping: () => invoke<{ ok: boolean }>("system.ping"),
  settings: {
    get: () => invoke("settings.get"),
    save: (params: Record<string, unknown>) => invoke("settings.save", params),
    saveHotkeys: (params: Record<string, unknown>) => invoke("settings.save_hotkeys", params),
    getLocalWhisperSetupInfo: () => invoke("settings.get_local_whisper_setup_info"),
    getLocalWhisperStatus: () => invoke("settings.get_local_whisper_status"),
    prepareLocalWhisperModel: () => invoke("settings.prepare_local_whisper_model"),
    installRnnoiseModel: () => ipcRenderer.invoke("yavervoice:select-rnnoise-model")
  },
  hotkeys: {
    status: () => invoke("hotkeys.status"),
    reload: () => invoke("hotkeys.reload")
  },
  devices: {
    microphones: () => invoke("devices.microphones"),
    recommendedMicrophone: () => invoke("devices.recommended_microphone")
  },
  recording: {
    toggle: () => invoke("recording.toggle"),
    status: () => invoke("recording.status")
  },
  files: {
    select: () => ipcRenderer.invoke("yavervoice:select-transcription-file"),
    checkDuration: (token: string) => invoke("files.check_duration", { token }),
    transcribe: (token: string) => invoke("files.transcribe", { token }),
    saveTranscript: (text: string, defaultFilename: string) => {
      return ipcRenderer.invoke("yavervoice:save-transcript", text, defaultFilename);
    }
  },
  split: {
    start: (token: string) => invoke("split.start", { token })
  },
  docs: {
    models: () => invoke("docs.models"),
    details: () => invoke("docs.details"),
    select: () => ipcRenderer.invoke("yavervoice:select-docs-file"),
    checkDuration: (token: string) => invoke("docs.check_duration", { token }),
    preflight: (token: string, model: string, detail: string, outputLanguage: string) => invoke("docs.preflight", { token, model, detail, output_language: outputLanguage }),
    createMarkdown: (token: string, defaultFilename: string, model: string, detail: string, outputLanguage: string) => {
      return ipcRenderer.invoke("yavervoice:create-docs-markdown", token, defaultFilename, model, detail, outputLanguage);
    },
    readFile: (path: string, directoryToken?: string) => ipcRenderer.invoke("yavervoice:read-docs-preview", { path, directoryToken }),
    selectDirectory: () => ipcRenderer.invoke("yavervoice:select-docs-directory"),
    listDirectory: (directoryToken: string) => ipcRenderer.invoke("yavervoice:list-docs-directory", directoryToken)
  },
  converter: {
    status: () => invoke("converter.status"),
    outputFormats: () => invoke("converter.output_formats"),
    select: () => ipcRenderer.invoke("yavervoice:select-converter-file"),
    convert: (token: string, outputFormat: string, defaultFilename: string) => {
      return ipcRenderer.invoke("yavervoice:convert-selected-file", token, outputFormat, defaultFilename);
    }
  },
  quick: {
    toggleRecording: () => invoke("quick.recording.toggle"),
    toggleWindow: () => ipcRenderer.invoke("yavervoice:quick-window-toggle"),
    showWindow: () => ipcRenderer.invoke("yavervoice:quick-window-show"),
    hideWindow: () => ipcRenderer.invoke("yavervoice:quick-window-hide"),
    showDashboard: () => ipcRenderer.invoke("yavervoice:quick-dashboard-show"),
    moveWindowBy: (deltaX: number, deltaY: number) => ipcRenderer.invoke("yavervoice:quick-window-move-by", deltaX, deltaY)
  },
  history: {
    list: () => invoke("history.list"),
    clear: () => invoke("history.clear"),
    updateText: (id: string, text: string) => invoke("history.update_text", { id, text }),
    delete: (id: string) => invoke("history.delete", { id }),
    createMerged: (text: string) => invoke("history.create_merged", { text })
  },
  clipboard: {
    copy: (text: string) => invoke("clipboard.copy", { text })
  },
  onSidecarLog: (callback: (entry: SidecarLogEntry) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, entry: SidecarLogEntry) => callback(entry);
    ipcRenderer.on("yavervoice:sidecar-log", listener);
    return () => ipcRenderer.off("yavervoice:sidecar-log", listener);
  },
  onSidecarEvent: (callback: (event: SidecarEvent) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, event: SidecarEvent) => callback(event);
    ipcRenderer.on("yavervoice:sidecar-event", listener);
    return () => ipcRenderer.off("yavervoice:sidecar-event", listener);
  }
};

contextBridge.exposeInMainWorld("yaverVoice", api);

export type YaverVoiceApi = typeof api;
