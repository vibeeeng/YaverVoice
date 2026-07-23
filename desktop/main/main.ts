import { app, BrowserWindow, Menu, Tray, dialog, ipcMain, screen } from "electron";
import type { IpcMainInvokeEvent, OpenDialogOptions, SaveDialogOptions } from "electron";
import { randomUUID } from "node:crypto";
import { existsSync, realpathSync, readdirSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { basename, dirname, extname, isAbsolute, join, relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { SidecarClient, SidecarError } from "./sidecarClient";

const linuxWaylandSession = process.platform === "linux"
  && Boolean(process.env.DISPLAY)
  && (
    process.env.XDG_SESSION_TYPE?.toLowerCase() === "wayland"
    || Boolean(process.env.WAYLAND_DISPLAY)
  );
if (linuxWaylandSession && !app.commandLine.hasSwitch("ozone-platform")) {
  app.commandLine.appendSwitch("ozone-platform", "x11");
}

const projectRoot = app.getAppPath();
const sidecar = new SidecarClient(projectRoot, {
  packaged: app.isPackaged,
  resourcesPath: process.resourcesPath
});

let mainWindow: BrowserWindow | null = null;
let quickWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let isQuitting = false;
let pendingStartupLog: { level: "debug" | "error"; message: string } | null = null;
const selectedDocsDirectories = new Map<string, string>();
const allowedDocsPreviewFiles = new Set<string>();
const quickEventMethods = new Set<string>(["recording.state", "quick.status"]);

type SenderRole = "main" | "quick";

function getDevRendererUrl(): string {
  const value = process.env.YAVERVOICE_RENDERER_URL ?? "http://127.0.0.1:5173";
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new SidecarError("YAVERVOICE_RENDERER_URL must be a valid loopback HTTP URL.");
  }
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname) || url.username || url.password) {
    throw new SidecarError("YAVERVOICE_RENDERER_URL must use http://127.0.0.1 or http://localhost.");
  }
  return url.href;
}

function configureWindowSecurity(window: BrowserWindow): void {
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event) => {
    event.preventDefault();
  });
}

async function stopRuntime(): Promise<void> {
  tray?.destroy();
  tray = null;
  await sidecar.stop();
}

function requestShutdown(): void {
  if (isQuitting) {
    return;
  }
  isQuitting = true;
  const forceExit = setTimeout(() => app.exit(0), 2500);
  forceExit.unref();
  void stopRuntime().finally(() => {
    clearTimeout(forceExit);
    if (app.isReady()) app.quit();
    else process.exit(0);
  });
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 620,
    minWidth: 900,
    minHeight: 560,
    title: "YaverVoice",
    backgroundColor: "#f6f7f9",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: join(projectRoot, "desktop", "dist", "preload", "preload.js")
    }
  });
  configureWindowSecurity(mainWindow);

  if (app.isPackaged) {
    void mainWindow.loadFile(join(projectRoot, "desktop", "dist", "renderer", "index.html"));
  } else {
    void mainWindow.loadURL(getDevRendererUrl());
  }

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      requestShutdown();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.webContents.once("did-finish-load", () => {
    if (pendingStartupLog) {
      const entry = pendingStartupLog;
      pendingStartupLog = null;
      setTimeout(() => {
        mainWindow?.webContents.send("yavervoice:sidecar-log", entry);
        mainWindow?.webContents.send("yavervoice:sidecar-event", {
          method: "toast",
          params: { type: entry.level, message: entry.message }
        });
      }, 500);
    }
  });
}

function createQuickWindow(): void {
  if (quickWindow) {
    return;
  }
  quickWindow = new BrowserWindow({
    width: 86,
    height: 76,
    minWidth: 86,
    minHeight: 76,
    frame: false,
    resizable: false,
    show: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    title: "YaverVoice Quick Dictation",
    backgroundColor: "#070A12",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: join(projectRoot, "desktop", "dist", "preload", "quickPreload.js")
    }
  });
  configureWindowSecurity(quickWindow);

  void quickWindow.loadFile(join(projectRoot, "desktop", "quick", "quick.html"));

  quickWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      quickWindow?.hide();
    }
  });

  quickWindow.on("closed", () => {
    quickWindow = null;
  });
}

function positionQuickWindow(): void {
  if (!quickWindow) {
    return;
  }
  const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const bounds = display.workArea;
  const [width, height] = quickWindow.getSize();
  quickWindow.setPosition(bounds.x + bounds.width - width - 24, bounds.y + bounds.height - height - 24);
}

function showQuickWindow(): { visible: boolean } {
  if (!quickWindow) {
    createQuickWindow();
  }
  positionQuickWindow();
  quickWindow?.show();
  quickWindow?.focus();
  return { visible: true };
}

function hideQuickWindow(): { visible: boolean } {
  quickWindow?.hide();
  return { visible: false };
}

function toggleQuickWindow(): { visible: boolean } {
  if (quickWindow?.isVisible()) {
    return hideQuickWindow();
  }
  return showQuickWindow();
}

function showDashboardFromQuick(): { success: boolean } {
  if (!mainWindow) {
    createWindow();
  }
  mainWindow?.show();
  mainWindow?.focus();
  return { success: true };
}

function moveQuickWindowBy(deltaX: number, deltaY: number): { success: boolean } {
  if (!quickWindow || !Number.isFinite(deltaX) || !Number.isFinite(deltaY)) {
    return { success: false };
  }
  const [x, y] = quickWindow.getPosition();
  quickWindow.setPosition(Math.round(x + deltaX), Math.round(y + deltaY), false);
  return { success: true };
}

function createTray(): void {
  if (tray) {
    return;
  }
  const iconPath = join(projectRoot, "logo", "logo1.png");
  tray = new Tray(iconPath);
  tray.setToolTip("YaverVoice");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      {
        label: "Restore",
        click: () => {
          if (!mainWindow) {
            createWindow();
          }
          mainWindow?.show();
          mainWindow?.focus();
        }
      },
      {
        label: "Quit",
        click: () => {
          requestShutdown();
        }
      }
    ])
  );
  tray.on("click", () => {
    mainWindow?.show();
    mainWindow?.focus();
  });
}

const mainSidecarMethods = new Set<string>([
  "system.ping",
  "settings.get",
  "settings.save",
  "settings.save_hotkeys",
  "settings.get_local_whisper_status",
  "settings.prepare_local_whisper_model",
  "hotkeys.status",
  "hotkeys.reload",
  "devices.microphones",
  "devices.recommended_microphone",
  "recording.toggle",
  "recording.status",
  "quick.recording.toggle",
  "files.check_duration",
  "files.transcribe",
  "split.start",
  "docs.models",
  "docs.details",
  "docs.check_duration",
  "docs.preflight",
  "converter.status",
  "converter.output_formats",
  "history.list",
  "history.clear",
  "history.update_text",
  "history.delete",
  "history.create_merged",
  "clipboard.copy"
]);

const quickSidecarMethods = new Set<string>(["recording.status", "quick.recording.toggle"]);

function getSenderRole(event: IpcMainInvokeEvent): SenderRole | null {
  if (!event.senderFrame || event.senderFrame !== event.sender.mainFrame) {
    return null;
  }
  const senderWindow = BrowserWindow.fromWebContents(event.sender);
  if (!senderWindow) {
    return null;
  }
  if (mainWindow && senderWindow.id === mainWindow.id && isExpectedRendererUrl("main", event.senderFrame.url)) {
    return "main";
  }
  if (quickWindow && senderWindow.id === quickWindow.id && isExpectedRendererUrl("quick", event.senderFrame.url)) {
    return "quick";
  }
  return null;
}

function isExpectedRendererUrl(role: SenderRole, frameUrl: string): boolean {
  try {
    const actual = new URL(frameUrl);
    if (role === "main" && !app.isPackaged) {
      const expected = new URL(getDevRendererUrl());
      return actual.origin === expected.origin;
    }
    const expectedPath = role === "main"
      ? join(projectRoot, "desktop", "dist", "renderer", "index.html")
      : join(projectRoot, "desktop", "quick", "quick.html");
    const expected = new URL(pathToFileURL(expectedPath).href);
    return actual.protocol === "file:" && actual.pathname === expected.pathname;
  } catch {
    return false;
  }
}

function requireSender(event: IpcMainInvokeEvent, roles: SenderRole[]): SenderRole {
  const role = getSenderRole(event);
  if (!role || !roles.includes(role)) {
    throw new SidecarError("IPC request is not available from this window.");
  }
  return role;
}

function requireMainSender(event: IpcMainInvokeEvent): void {
  requireSender(event, ["main"]);
}

function requireQuickSender(event: IpcMainInvokeEvent): void {
  requireSender(event, ["quick"]);
}

function isPathInside(parentPath: string, childPath: string): boolean {
  const childRelativePath = relative(parentPath, childPath);
  return childRelativePath === "" || Boolean(childRelativePath && !childRelativePath.startsWith("..") && !isAbsolute(childRelativePath));
}

function resolveExistingMarkdownPath(filePath: string): string {
  if (typeof filePath !== "string" || !filePath.trim()) {
    throw new SidecarError("Invalid file path.");
  }
  if (!filePath.toLowerCase().endsWith(".md")) {
    throw new SidecarError("Only markdown files can be previewed.");
  }
  const resolvedPath = realpathSync(resolve(filePath));
  if (!resolvedPath.toLowerCase().endsWith(".md") || !statSync(resolvedPath).isFile()) {
    throw new SidecarError("Only markdown files can be previewed.");
  }
  return resolvedPath;
}

function getSelectedDocsDirectory(directoryToken: string): string {
  const directoryPath = selectedDocsDirectories.get(directoryToken);
  if (!directoryPath) {
    throw new SidecarError("Docs directory must be selected from the app before preview.");
  }
  return directoryPath;
}

function withFileExtension(filePath: string, extension: string): string {
  if (filePath.toLowerCase().endsWith(extension)) {
    return filePath;
  }
  const currentExtension = extname(filePath);
  if (!currentExtension) {
    return `${filePath}${extension}`;
  }
  return join(dirname(filePath), `${basename(filePath, currentExtension)}${extension}`);
}

ipcMain.handle("yavervoice:invoke", async (event, method: string, params?: Record<string, unknown>) => {
  if (typeof method !== "string" || !method.trim()) {
    throw new SidecarError("Invalid sidecar method.");
  }
  const role = requireSender(event, ["main", "quick"]);
  const sidecarMethod = method.trim();
  const allowedMethods = role === "quick" ? quickSidecarMethods : mainSidecarMethods;
  if (!allowedMethods.has(sidecarMethod)) {
    throw new SidecarError("Sidecar method is not available from this window.");
  }
  return sidecar.invoke(sidecarMethod, params ?? {});
});

const mediaFilters = [
  { name: "Audio and Video", extensions: ["mp3", "wav", "m4a", "ogg", "flac", "aac", "wma", "opus", "mp4", "mkv", "webm"] },
  { name: "All Files", extensions: ["*"] }
];

ipcMain.handle("yavervoice:select-transcription-file", async (event) => {
  requireMainSender(event);
  const options: OpenDialogOptions = {
    title: "Select Audio File",
    properties: ["openFile"],
    filters: mediaFilters
  };
  const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options);
  if (result.canceled || !result.filePaths[0]) {
    return null;
  }
  const selectedPath = result.filePaths[0];
  ensureSelectedFileIsAccessible(selectedPath);
  return sidecar.invoke("files.register_selected", { path: selectedPath });
});

ipcMain.handle("yavervoice:select-docs-file", async (event) => {
  requireMainSender(event);
  const options: OpenDialogOptions = {
    title: "Select Audio or Video File",
    properties: ["openFile"],
    filters: mediaFilters
  };
  const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options);
  if (result.canceled || !result.filePaths[0]) {
    return null;
  }
  const selectedPath = result.filePaths[0];
  ensureSelectedFileIsAccessible(selectedPath);
  return sidecar.invoke("docs.register_selected", { path: selectedPath });
});

ipcMain.handle("yavervoice:select-rnnoise-model", async (event) => {
  requireMainSender(event);
  const options: OpenDialogOptions = {
    title: "Select RNNoise Model",
    properties: ["openFile"],
    filters: [
      { name: "RNNoise Model", extensions: ["rnnn"] },
      { name: "All Files", extensions: ["*"] }
    ]
  };
  const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options);
  if (result.canceled || !result.filePaths[0]) {
    return null;
  }
  const selectedPath = result.filePaths[0];
  ensureSelectedFileIsAccessible(selectedPath);
  return sidecar.invoke("settings.install_rnnoise_model", { path: selectedPath });
});

ipcMain.handle("yavervoice:quick-window-toggle", (event) => {
  requireMainSender(event);
  return toggleQuickWindow();
});
ipcMain.handle("yavervoice:quick-window-show", (event) => {
  requireMainSender(event);
  return showQuickWindow();
});
ipcMain.handle("yavervoice:quick-window-hide", (event) => {
  requireQuickSender(event);
  return hideQuickWindow();
});
ipcMain.handle("yavervoice:quick-dashboard-show", (event) => {
  requireQuickSender(event);
  return showDashboardFromQuick();
});
ipcMain.handle("yavervoice:quick-window-move-by", (event, deltaX: number, deltaY: number) => {
  requireQuickSender(event);
  return moveQuickWindowBy(deltaX, deltaY);
});

ipcMain.handle("yavervoice:select-converter-file", async (event) => {
  requireMainSender(event);
  const options: OpenDialogOptions = {
    title: "Dönüştürülecek Dosyayı Seç",
    properties: ["openFile"],
    filters: mediaFilters
  };
  const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options);
  if (result.canceled || !result.filePaths[0]) {
    return null;
  }
  const selectedPath = result.filePaths[0];
  ensureSelectedFileIsAccessible(selectedPath);
  return sidecar.invoke("converter.register_selected", { path: selectedPath });
});

ipcMain.handle("yavervoice:save-transcript", async (event, text: string, defaultFilename: string) => {
  requireMainSender(event);
  if (typeof text !== "string") {
    throw new SidecarError("Invalid transcript text.");
  }
  const options: SaveDialogOptions = {
    title: "Transcripti Kaydet",
    defaultPath: sanitizeDefaultFilename(defaultFilename || "transcript.txt"),
    filters: [
      { name: "Metin Dosyaları", extensions: ["txt"] },
      { name: "All Files", extensions: ["*"] }
    ]
  };
  const result = mainWindow ? await dialog.showSaveDialog(mainWindow, options) : await dialog.showSaveDialog(options);
  if (result.canceled || !result.filePath) {
    return { success: false, cancelled: true };
  }
  return sidecar.invoke("files.save_transcript", { text, path: result.filePath });
});

ipcMain.handle("yavervoice:create-docs-markdown", async (event, token: string, defaultFilename: string, model: string, detail: string, outputLanguage: string) => {
  requireMainSender(event);
  if (typeof token !== "string" || !token.trim()) {
    throw new SidecarError("Invalid Docs request.");
  }
  const options: SaveDialogOptions = {
    title: "Markdown Dokümanı Kaydet",
    defaultPath: sanitizeDefaultFilename(defaultFilename || "docs.md"),
    filters: [
      { name: "Markdown", extensions: ["md"] },
      { name: "All Files", extensions: ["*"] }
    ]
  };
  const result = mainWindow ? await dialog.showSaveDialog(mainWindow, options) : await dialog.showSaveDialog(options);
  if (result.canceled || !result.filePath) {
    return { success: false, cancelled: true, message: "İptal edildi" };
  }
  const outputPath = withFileExtension(result.filePath, ".md");
  allowedDocsPreviewFiles.add(resolve(outputPath));
  return sidecar.invoke("docs.start", { token, path: outputPath, model, detail, output_language: outputLanguage });
});

ipcMain.handle("yavervoice:read-docs-preview", async (event, request: { path?: string; directoryToken?: string }) => {
  requireMainSender(event);
  if (!request || typeof request.path !== "string") {
    throw new SidecarError("Invalid file path.");
  }
  const previewPath = resolveExistingMarkdownPath(request.path);
  if (typeof request.directoryToken === "string" && request.directoryToken.trim()) {
    const directoryPath = getSelectedDocsDirectory(request.directoryToken);
    if (!isPathInside(directoryPath, previewPath)) {
      throw new SidecarError("Preview file must be inside the selected Docs directory.");
    }
  } else if (!allowedDocsPreviewFiles.has(previewPath)) {
    throw new SidecarError("Preview file must be selected or generated from the app before use.");
  }
  const content = await readFile(previewPath, "utf-8");
  return { content, path: previewPath };
});

ipcMain.handle("yavervoice:select-docs-directory", async (event) => {
  requireMainSender(event);
  const options: OpenDialogOptions = {
    title: "Docs klasörü seç",
    properties: ["openDirectory"]
  };
  const result = mainWindow ? await dialog.showOpenDialog(mainWindow, options) : await dialog.showOpenDialog(options);
  if (result.canceled || !result.filePaths[0]) {
    return null;
  }
  const directoryPath = realpathSync(result.filePaths[0]);
  const token = randomUUID();
  selectedDocsDirectories.set(token, directoryPath);
  return { token, path: directoryPath };
});

ipcMain.handle("yavervoice:list-docs-directory", async (event, directoryToken: string) => {
  requireMainSender(event);
  if (typeof directoryToken !== "string" || !directoryToken.trim()) {
    throw new SidecarError("Invalid directory token.");
  }
  const dirPath = getSelectedDocsDirectory(directoryToken);
  if (!existsSync(dirPath) || !statSync(dirPath).isDirectory()) {
    return [];
  }
  const entries = readdirSync(dirPath).flatMap((name) => {
    if (!name.toLowerCase().endsWith(".md")) {
      return [];
    }
    try {
      const path = realpathSync(join(dirPath, name));
      if (statSync(path).isFile() && isPathInside(dirPath, path)) {
        return [{ name, path }];
      }
    } catch {
      return [];
    }
    return [];
  });
  return entries;
});

ipcMain.handle(
  "yavervoice:convert-selected-file",
  async (event, token: string, outputFormat: string, defaultFilename: string) => {
    requireMainSender(event);
    if (typeof token !== "string" || typeof outputFormat !== "string") {
      throw new SidecarError("Invalid converter request.");
    }
    const extension = outputFormat.replace(/[^A-Za-z0-9]/g, "") || "mp3";
    const options: SaveDialogOptions = {
      title: "Dönüştürülen Dosyayı Kaydet",
      defaultPath: sanitizeDefaultFilename(defaultFilename || `converted.${extension}`),
      filters: [
        { name: outputFormat.toUpperCase(), extensions: [extension] },
        { name: "All Files", extensions: ["*"] }
      ]
    };
    const result = mainWindow ? await dialog.showSaveDialog(mainWindow, options) : await dialog.showSaveDialog(options);
    if (result.canceled || !result.filePath) {
      return { success: false, cancelled: true, message: "İptal edildi" };
    }
    return sidecar.invoke("converter.convert", {
      token,
      output_format: outputFormat,
      path: result.filePath
    });
  }
);

sidecar.on("log", (entry: { level: "debug" | "error"; message: string }) => {
  mainWindow?.webContents.send("yavervoice:sidecar-log", entry);
});

sidecar.on("event", (event: { method: string; params: Record<string, unknown> }) => {
  if (event.method === "app.shutdown") {
    requestShutdown();
    return;
  }
  mainWindow?.webContents.send("yavervoice:sidecar-event", event);
  if (quickEventMethods.has(event.method)) {
    quickWindow?.webContents.send("yavervoice:sidecar-event", event);
  }
});

app.whenReady().then(async () => {
  app.setName("YaverVoice");
  app.setAboutPanelOptions({
    applicationName: "YaverVoice",
    applicationVersion: app.getVersion(),
    copyright: "YaverVoice"
  });

  try {
    await sidecar.start();
  } catch (error) {
    pendingStartupLog = {
      level: "error",
      message: error instanceof Error ? error.message : "Failed to start the YaverVoice sidecar."
    };
    sidecar.emit("log", pendingStartupLog);
  }
  createWindow();
  createQuickWindow();
  createTray();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    requestShutdown();
  }
});

app.on("before-quit", (event) => {
  if (!isQuitting) {
    event.preventDefault();
    requestShutdown();
  }
});

process.once("SIGINT", requestShutdown);
process.once("SIGTERM", requestShutdown);

function sanitizeDefaultFilename(value: string): string {
  const cleaned = value.replace(/[\x00-\x1f\x7f<>:"/\\|?*]+/g, "_").trim();
  return cleaned || "transcript.txt";
}

function ensureSelectedFileIsAccessible(filePath: string): void {
  if (!existsSync(filePath)) {
    throw new SidecarError("Selected file is not accessible. Check that the file still exists and try again.");
  }
}
