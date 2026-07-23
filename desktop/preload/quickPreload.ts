import { contextBridge, ipcRenderer } from "electron";

type SidecarEvent = {
  method: string;
  params: Record<string, unknown>;
};

const invoke = <T>(method: string, params?: Record<string, unknown>): Promise<T> => {
  return ipcRenderer.invoke("yavervoice:invoke", method, params ?? {}) as Promise<T>;
};

const api = {
  platform: process.platform,
  recording: {
    status: () => invoke("recording.status")
  },
  quick: {
    toggleRecording: () => invoke("quick.recording.toggle"),
    hideWindow: () => ipcRenderer.invoke("yavervoice:quick-window-hide"),
    showDashboard: () => ipcRenderer.invoke("yavervoice:quick-dashboard-show"),
    moveWindowBy: (deltaX: number, deltaY: number) => ipcRenderer.invoke("yavervoice:quick-window-move-by", deltaX, deltaY)
  },
  onSidecarEvent: (callback: (event: SidecarEvent) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, event: SidecarEvent) => callback(event);
    ipcRenderer.on("yavervoice:sidecar-event", listener);
    return () => ipcRenderer.off("yavervoice:sidecar-event", listener);
  }
};

contextBridge.exposeInMainWorld("yaverVoice", api);
