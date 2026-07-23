import { Cloud, HardDrive } from "lucide-react";

import type { Settings } from "../types/yaverVoice";

export type ProcessingContextMode = "transcription" | "notes-generation" | "media-conversion";

export function ProcessingContextBadge({
  settings,
  compact = false,
  mode = "transcription",
  label
}: {
  settings: Settings | null;
  compact?: boolean;
  mode?: ProcessingContextMode;
  label?: string;
}) {
  const local = mode === "transcription" && settings?.transcription_provider === "local";
  const provider = mode === "notes-generation"
    ? "Groq Cloud"
    : mode === "media-conversion"
      ? "FFmpeg"
      : settings
        ? local ? "Local Whisper" : "Groq Cloud"
        : "Provider loading";
  const location = mode === "media-conversion"
    ? "On-device"
    : mode === "notes-generation"
      ? "Cloud processing"
      : settings
        ? local ? "On-device" : "Cloud processing"
        : "Waiting for settings";
  const contextLabel = label ?? (mode === "media-conversion" ? "Media conversion" : mode === "notes-generation" ? "Notes generation" : "Transcription");
  const Icon = mode === "media-conversion" || local ? HardDrive : Cloud;

  return (
    <span
      className={compact ? "processingContext compact" : "processingContext"}
      aria-label={`${contextLabel}. Provider: ${provider}. Location: ${location}.`}
    >
      {label && <span className="processingContextLabel">{label}</span>}
      <Icon size={compact ? 13 : 14} aria-hidden="true" />
      <span className="processingProvider">{provider}</span>
      {!compact && <span className="processingLocation">{location}</span>}
    </span>
  );
}
