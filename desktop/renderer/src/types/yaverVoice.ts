export type LocalWhisperStatus = {
  dependency_installed?: boolean;
  dependency_available?: boolean;
  model_exists?: boolean;
  model_path?: string;
  model_dir?: string;
  managed_model_dir?: string;
  model_source?: string;
  message?: string;
  status?: string;
  transcription_ready?: boolean;
  translation_ready?: boolean;
  profile?: string;
  model?: string;
  device?: string;
  compute_type?: string;
  cpu_usage?: string;
  error?: string | null;
  [key: string]: unknown;
};

export type Settings = {
  api_key_exists: boolean;
  api_key_length: number;
  transcription_provider: "groq" | "local";
  local_whisper_profile: string;
  local_whisper_model: string;
  local_whisper_device: string;
  local_whisper_compute_type: string;
  local_whisper_cpu_usage: string;
  local_whisper_cpu_threads?: number | string;
  local_whisper_status?: LocalWhisperStatus;
  build_version: string;
  build_display: string;
  input_device_index: number;
  recommended_microphone_index: number;
  sound_enabled: boolean;
  auto_paste_enabled: boolean;
  toggle_recording_auto_paste_enabled: boolean;
  audio_cleanup_mode: "off" | "normal" | "noisy" | "severe";
  audio_cleanup_enabled: boolean;
  audio_cleanup_status?: {
    rnnoise_ready: boolean;
    rnnoise_model_path: string | null;
    managed_model_dir: string;
    arnndn_available: boolean;
    message: string;
  };
  always_on_top: boolean;
  translate_enabled: boolean;
  language: string;
  recording_trigger_mode: "hold_to_talk" | "toggle";
  push_to_talk_key: string;
  push_to_talk_key_display: string;
  toggle_hotkey: string;
  toggle_hotkey_display: string;
  translate_toggle_hotkey: string;
  translate_toggle_hotkey_display: string;
  recording_hotkey?: string;
  recording_hotkey_display?: string;
};

export type HistoryItem = {
  id: string;
  timestamp: string;
  text: string;
  transcribed: boolean;
  is_split?: boolean;
  chunk_part?: number | null;
  parent_recording_id?: string | null;
};

export type MicrophoneDevice = {
  index: number;
  name: string;
  [key: string]: unknown;
};

export type SelectedFile = {
  token: string;
  name: string;
  extension: string;
  size_bytes: number;
  size_mb: number;
  display_path?: string;
};

export type RecordingStatus = {
  recording: boolean;
  transcribing: boolean;
  mode: string;
};

export type FfmpegStatus = {
  installed: boolean;
  ffmpeg_installed?: boolean;
  ffprobe_installed?: boolean;
  ffmpeg_path?: string | null;
  ffprobe_path?: string | null;
  version?: string | null;
};

export type OutputFormat = {
  key: string;
  ext: string;
  name: string;
};

export type FileDuration = {
  duration_seconds: number;
  duration_minutes: number;
  should_split: boolean;
  threshold_seconds: number;
  file_size_mb: number;
  force_split_by_size: boolean;
  provider: string;
};

export type DocsModelProfile = {
  id: string;
  label: string;
  note: string;
  chunk_chars: number;
  chunk_max_tokens: number;
  final_max_tokens: number;
  tpm: string;
  tpd: string;
};

export type DocsDetailProfile = {
  id: string;
  label: string;
  note: string;
  chunk_multiplier: number;
  final_multiplier: number;
  instruction: string;
};

export type DocsPreflight = {
  ready: boolean;
  blockers: string[];
  warnings: string[];
  provider: string;
  model?: string | null;
  model_label?: string | null;
  detail?: string | null;
  detail_label?: string | null;
  output_language?: string | null;
  output_language_label?: string | null;
};

export type DocsDirectorySelection = {
  token: string;
  path: string;
};

export type SidecarLogEntry = {
  level: "debug" | "error";
  message: string;
};

export type HotkeysStatus = {
  enabled: boolean;
  registered: boolean;
  status: string;
  error?: string | null;
  push_to_talk_key?: string;
  toggle_hotkey?: string;
  translate_toggle_hotkey?: string;
};

export type SidecarEvent =
  | {
      method: "history.updated";
      params: { history: HistoryItem[] };
    }
  | {
      method: "settings.changed";
      params: { config: Settings };
    }
  | {
      method: "recording.state";
      params: RecordingStatus;
    }
  | {
      method: string;
      params: Record<string, unknown>;
    };

export type YaverVoiceApi = {
  ping: () => Promise<{ ok: boolean }>;
  settings: {
    get: () => Promise<Settings>;
    save: (params: Record<string, unknown>) => Promise<Settings>;
    saveHotkeys: (params: Record<string, unknown>) => Promise<{ success: boolean; message: string; config: Settings }>;
    getLocalWhisperStatus: () => Promise<LocalWhisperStatus>;
    prepareLocalWhisperModel: () => Promise<Record<string, unknown>>;
    installRnnoiseModel: () => Promise<{ success: boolean; message: string; config: Settings } | null>;
  };
  hotkeys: {
    status: () => Promise<HotkeysStatus>;
    reload: () => Promise<HotkeysStatus>;
  };
  devices: {
    microphones: () => Promise<MicrophoneDevice[]>;
    recommendedMicrophone: () => Promise<{ index: number }>;
  };
  recording: {
    toggle: () => Promise<RecordingStatus>;
    status: () => Promise<RecordingStatus>;
  };
  files: {
    select: () => Promise<SelectedFile | null>;
    checkDuration: (token: string) => Promise<FileDuration>;
    transcribe: (token: string) => Promise<{ success: boolean; accepted?: boolean; id: string; message?: string; history: HistoryItem[] }>;
    saveTranscript: (text: string, defaultFilename: string) => Promise<{ success: boolean; cancelled?: boolean }>;
  };
  split: {
    start: (token: string) => Promise<{ success: boolean; accepted?: boolean; recording_id: string; success_count: number; failed_chunks: number[]; message?: string; history: HistoryItem[] }>;
  };
  docs: {
    models: () => Promise<DocsModelProfile[]>;
    details: () => Promise<DocsDetailProfile[]>;
    select: () => Promise<SelectedFile | null>;
    checkDuration: (token: string) => Promise<FileDuration>;
    preflight: (token: string, model: string, detail: string, outputLanguage: string) => Promise<DocsPreflight>;
    createMarkdown: (token: string, defaultFilename: string, model: string, detail: string, outputLanguage: string) => Promise<{ success: boolean; accepted?: boolean; cancelled?: boolean; id?: string; model?: string; model_label?: string; detail?: string; detail_label?: string; output_language?: string; output_language_label?: string; message?: string; history?: HistoryItem[] }>;
    readFile: (path: string, directoryToken?: string) => Promise<{ content: string; path: string }>;
    selectDirectory: () => Promise<DocsDirectorySelection | null>;
    listDirectory: (directoryToken: string) => Promise<Array<{ name: string; path: string }>>;
  };
  converter: {
    status: () => Promise<FfmpegStatus>;
    outputFormats: () => Promise<OutputFormat[]>;
    select: () => Promise<SelectedFile | null>;
    convert: (token: string, outputFormat: string, defaultFilename: string) => Promise<{ success: boolean; accepted?: boolean; cancelled?: boolean; message?: string }>;
  };
  quick: {
    toggleRecording: () => Promise<RecordingStatus>;
    toggleWindow: () => Promise<{ visible: boolean }>;
    showWindow: () => Promise<{ visible: boolean }>;
    hideWindow: () => Promise<{ visible: boolean }>;
    showDashboard: () => Promise<{ success: boolean }>;
    moveWindowBy: (deltaX: number, deltaY: number) => Promise<{ success: boolean }>;
  };
  history: {
    list: () => Promise<HistoryItem[]>;
    clear: () => Promise<{ success: boolean; history: HistoryItem[] }>;
    updateText: (id: string, text: string) => Promise<{ success: boolean; history: HistoryItem[] }>;
    delete: (id: string) => Promise<{ success: boolean; history: HistoryItem[] }>;
    createMerged: (text: string) => Promise<{ success: boolean; id: string; history: HistoryItem[] }>;
  };
  clipboard: {
    copy: (text: string) => Promise<{ success: boolean }>;
  };
  onSidecarLog: (callback: (entry: SidecarLogEntry) => void) => () => void;
  onSidecarEvent: (callback: (event: SidecarEvent) => void) => () => void;
};

declare global {
  interface Window {
    yaverVoice: YaverVoiceApi;
  }
}
