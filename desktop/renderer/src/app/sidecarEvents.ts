import type React from "react";

import type { HistoryItem, RecordingStatus, Settings, SidecarEvent } from "../types/yaverVoice";
import type { GlobalProgressEntry, ToastMessage } from "../types/ui";
import { clamp } from "../utils/formatters";

export function handleSidecarEvent(
  event: SidecarEvent,
  setSettings: React.Dispatch<React.SetStateAction<Settings | null>>,
  setHistory: React.Dispatch<React.SetStateAction<HistoryItem[]>>,
  setRecordingStatus: React.Dispatch<React.SetStateAction<RecordingStatus>>,
  pushToast: (message: string, type?: ToastMessage["type"]) => void,
  setMessage: React.Dispatch<React.SetStateAction<string>>,
  updateGlobalProgress: (entry: GlobalProgressEntry) => void,
  clearGlobalProgress: (source: GlobalProgressEntry["source"]) => void
) {
  if (event.method === "history.updated" && Array.isArray(event.params.history)) {
    setHistory(event.params.history as HistoryItem[]);
  }
  if (event.method === "settings.changed" && event.params.config) {
    setSettings(event.params.config as Settings);
  }
  if (event.method === "recording.state") {
    setRecordingStatus(event.params as RecordingStatus);
  }
  if (event.method === "toast" && typeof event.params.message === "string") {
    const eventType = typeof event.params.type === "string" ? event.params.type : "info";
    pushToast(event.params.message, eventType as ToastMessage["type"]);
  }
  if ((event.method === "quick.status" || event.method === "file.status" || event.method === "converter.status" || event.method === "docs.status") && typeof event.params.message === "string") {
    setMessage(event.params.message);
    if (event.method === "converter.status") {
      pushToast(event.params.message, event.params.success === false ? "error" : "info");
    }
  }
  if (event.method === "split.step") {
    const state = typeof event.params.state === "string" ? event.params.state : "split";
    const total = typeof event.params.total_parts === "number" ? ` (${event.params.total_parts} parts)` : "";
    const message = typeof event.params.message === "string" ? event.params.message : `Split workflow: ${state}${total}`;
    setMessage(message);
  }
  if (event.method === "split.progress") {
    setMessage(`Split transcription: ${event.params.current ?? "?"}/${event.params.total ?? "?"}`);
  }

  // Global progress tracking
  if (event.method === "docs.status" || event.method === "docs.progress") {
    const eventState = typeof event.params.state === "string" ? event.params.state as string : null;
    const percent = typeof event.params.percent === "number" ? event.params.percent as number : null;
    const phase = typeof event.params.phase === "string" ? event.params.phase as string : null;
    if (eventState === "complete") {
      clearGlobalProgress("docs");
    } else if (eventState === "error") {
      clearGlobalProgress("docs");
    } else if (percent !== null) {
      const label = phase === "splitting" ? "Splitting" : phase === "transcribing" ? "Transcribing" : phase === "summarizing" ? "Summarizing" : phase === "writing" ? "Writing" : "Docs";
      updateGlobalProgress({ source: "docs", percent: clamp(percent, 0, 100), state: "active", label });
    }
  }
  if (event.method === "file.status") {
    const eventState = typeof event.params.state === "string" ? event.params.state as string : null;
    const percent = typeof event.params.percent === "number" ? event.params.percent as number : null;
    if (eventState === "complete" || eventState === "error") {
      clearGlobalProgress("files");
    } else if (percent !== null) {
      updateGlobalProgress({ source: "files", percent: clamp(percent, 0, 100), state: "active", label: "Transcribing" });
    }
  }
  if (event.method === "split.step") {
    const eventState = typeof event.params.state === "string" ? event.params.state as string : null;
    if (eventState === "complete" || eventState === "error") {
      clearGlobalProgress("files");
    } else {
      const percent = eventState === "split_complete" ? 20 : 10;
      updateGlobalProgress({ source: "files", percent, state: "active", label: "Splitting" });
    }
  }
  if (event.method === "split.progress") {
    const current = typeof event.params.current === "number" ? event.params.current as number : 0;
    const total = typeof event.params.total === "number" && (event.params.total as number) > 0 ? event.params.total as number : 0;
    if (total > 0) {
      updateGlobalProgress({ source: "files", percent: clamp(20 + (current / total) * 75, 20, 95), state: "active", label: "Transcribing" });
    }
  }
  if (event.method === "converter.status") {
    const eventState = typeof event.params.state === "string" ? event.params.state as string : null;
    if (eventState === "complete" || eventState === "error") {
      clearGlobalProgress("converter");
    }
  }
}
