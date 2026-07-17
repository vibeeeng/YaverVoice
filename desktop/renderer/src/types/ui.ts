export type WorkspaceId = "capture" | "files" | "library" | "settings";
export type CaptureMode = "quick" | "record";
export type FilesMode = "transcribe" | "notes" | "convert";

// Retained until a separately authorized cleanup removes the unused Home view.
export type SectionId = "home" | "settings" | "history" | "record" | "files" | "docs" | "converter" | "quick";

export type ToastMessage = {
  id: number;
  message: string;
  type: "success" | "error" | "warning" | "info";
};

export type GlobalProgressEntry = {
  source: "docs" | "files" | "converter";
  percent: number;
  state: "active" | "complete" | "error";
  label: string;
};

export type DocsOutputLanguage = "same" | "tr" | "en" | "de" | "fr" | "es" | "it";

export type LocalInfoLanguage = "tr" | "en";
