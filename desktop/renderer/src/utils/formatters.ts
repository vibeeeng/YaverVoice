import type { DocsModelProfile, FileDuration } from "../types/yaverVoice";
import type { DocsOutputLanguage } from "../types/ui";

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function formatAudioDuration(duration: FileDuration | null): string {
  if (!duration || duration.duration_seconds <= 0) {
    return "Duration unknown";
  }
  const totalSeconds = Math.round(duration.duration_seconds);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function estimateDocsCallsFromDuration(duration: FileDuration | null, model: DocsModelProfile): number {
  if (!duration || duration.duration_seconds <= 0) {
    return 1;
  }
  const estimatedTranscriptChars = Math.max(1000, Math.round(duration.duration_seconds * 16));
  const chunkCount = Math.max(1, Math.ceil(estimatedTranscriptChars / model.chunk_chars));
  return chunkCount === 1 ? 1 : chunkCount + 1;
}

export function docsOutputLanguageFromSettings(language?: string): DocsOutputLanguage {
  const normalized = (language ?? "auto").toLowerCase();
  if (normalized === "tr" || normalized === "en" || normalized === "de" || normalized === "fr" || normalized === "es" || normalized === "it") {
    return normalized;
  }
  return "same";
}

export function formatDocsLogEntry(message: string, params: Record<string, unknown>): string {
  const state = typeof params.state === "string" ? params.state : "status";
  if (state === "complete" && typeof params.calls === "number") {
    const totalTokens = typeof params.total_tokens === "number" && params.total_tokens > 0
      ? ` · ${params.total_tokens} tokens`
      : "";
    return `Complete · ${params.calls} model calls${totalTokens}`;
  }
  if (state === "summarizing" && typeof params.estimated_calls === "number") {
    const detail = typeof params.detail_label === "string" ? ` · ${params.detail_label}` : "";
    const outputLanguage = typeof params.output_language_label === "string" ? ` · ${params.output_language_label}` : "";
    return `Summarizing${detail}${outputLanguage} · ${params.estimated_calls} estimated model calls`;
  }
  return message;
}

export function formatDocsProgressEntry(message: string, params: Record<string, unknown>): string {
  const phase = typeof params.phase === "string" ? params.phase : "processing";
  const current = typeof params.current === "number" ? params.current : null;
  const total = typeof params.total === "number" ? params.total : null;
  if (phase === "summarizing" && current !== null && total !== null) {
    return `Summarizing · ${current}/${total} model calls`;
  }
  if (phase === "writing") {
    return "Writing Markdown file";
  }
  if (phase === "transcribing" && current !== null && total !== null) {
    return `Transcribing split part ${current}/${total}`;
  }
  return message;
}

export function formatDocsPhaseLabel(phase: string): string {
  if (phase === "splitting") {
    return "Splitting";
  }
  if (phase === "transcribing") {
    return "Transcribing";
  }
  if (phase === "summarizing") {
    return "Summarizing";
  }
  if (phase === "writing") {
    return "Writing";
  }
  if (phase === "complete") {
    return "Complete";
  }
  if (phase === "error") {
    return "Failed";
  }
  return "Processing";
}
