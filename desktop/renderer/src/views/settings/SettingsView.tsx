import { useEffect, useState } from "react";
import { Check, Clipboard, Cloud, HardDrive, Languages, Volume2, Wand2 } from "lucide-react";

import { Toggle } from "../../components/Toggle";
import type { FfmpegStatus, MicrophoneDevice, Settings } from "../../types/yaverVoice";
import type { LocalInfoLanguage, ToastMessage } from "../../types/ui";
import { formatHotkeyDisplay, hotkeyFromKeyboardEvent } from "../../utils/hotkeys";
import { LocalWhisperInfoDialog } from "./LocalWhisperInfoDialog";
import { RnnoiseInfoDialog } from "./RnnoiseInfoDialog";
import { localWhisperInfoCopy } from "./localWhisperInfo";

type SettingsCategory = "transcription" | "audio" | "behavior" | "hotkeys" | "system";

const settingsCategories: Array<{ id: SettingsCategory; label: string }> = [
  { id: "transcription", label: "Transcription" },
  { id: "audio", label: "Audio" },
  { id: "behavior", label: "Behavior" },
  { id: "hotkeys", label: "Hotkeys" },
  { id: "system", label: "System status" }
];

export function SettingsView({
  settings,
  onSettings,
  pushToast
}: {
  settings: Settings;
  onSettings: (settings: Settings) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [draft, setDraft] = useState(settings);
  const [apiKey, setApiKey] = useState("");
  const [apiKeyEditing, setApiKeyEditing] = useState(false);
  const [notice, setNotice] = useState("");
  const [microphones, setMicrophones] = useState<MicrophoneDevice[]>([]);
  const [ffmpegStatus, setFfmpegStatus] = useState<FfmpegStatus | null>(null);
  const [hotkeyCapture, setHotkeyCapture] = useState<null | "push_to_talk" | "toggle_recording" | "translate">(null);
  const [capturedHotkey, setCapturedHotkey] = useState("");
  const [localAdvancedOpen, setLocalAdvancedOpen] = useState(false);
  const [localInfoOpen, setLocalInfoOpen] = useState(false);
  const [rnnoiseInfoOpen, setRnnoiseInfoOpen] = useState(false);
  const [localInfoLanguage, setLocalInfoLanguage] = useState<LocalInfoLanguage>("tr");
  const [activeCategory, setActiveCategory] = useState<SettingsCategory>("transcription");

  useEffect(() => {
    setDraft(settings);
  }, [settings]);

  useEffect(() => {
    void Promise.allSettled([
      window.yaverVoice.devices.microphones(),
      window.yaverVoice.converter.status()
    ]).then(([deviceResult, ffmpegResult]) => {
      if (deviceResult.status === "fulfilled") {
        setMicrophones(deviceResult.value);
      }
      if (ffmpegResult.status === "fulfilled") {
        setFfmpegStatus(ffmpegResult.value);
      }
    });
  }, []);

  useEffect(() => {
    if (!hotkeyCapture) {
      return undefined;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      event.preventDefault();
      setCapturedHotkey(hotkeyFromKeyboardEvent(event, hotkeyCapture === "push_to_talk"));
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [hotkeyCapture]);

  useEffect(() => {
    if (!localInfoOpen && !rnnoiseInfoOpen) {
      return undefined;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setLocalInfoOpen(false);
        setRnnoiseInfoOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [localInfoOpen, rnnoiseInfoOpen]);

  const saveSettings = async () => {
    try {
      const payload: Record<string, unknown> = {
        transcription_provider: draft.transcription_provider,
        language: draft.language,
        input_device_index: draft.input_device_index,
        translate_enabled: draft.translate_enabled,
        sound_enabled: draft.sound_enabled,
        auto_paste_enabled: draft.auto_paste_enabled,
        toggle_recording_auto_paste_enabled: draft.toggle_recording_auto_paste_enabled,
        audio_cleanup_mode: draft.audio_cleanup_mode,
        always_on_top: draft.always_on_top,
        local_whisper_profile: draft.local_whisper_profile,
        local_whisper_device: draft.local_whisper_device,
        local_whisper_compute_type: draft.local_whisper_compute_type,
        local_whisper_cpu_usage: draft.local_whisper_cpu_usage
      };
      if (apiKey.trim()) {
        payload.api_key = apiKey.trim();
      }
      const nextSettings = await window.yaverVoice.settings.save(payload);
      onSettings(nextSettings);
      setApiKey("");
      setApiKeyEditing(false);
      setNotice("Settings saved.");
      pushToast("Settings saved", "success");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Settings save failed.");
      pushToast(error instanceof Error ? error.message : "Settings save failed.", "error");
    }
  };

  const savePartialSettings = async (payload: Record<string, unknown>, toast: string) => {
    try {
      const nextSettings = await window.yaverVoice.settings.save(payload);
      onSettings(nextSettings);
      setDraft(nextSettings);
      setNotice(toast);
      pushToast(toast, "info");
    } catch (error) {
      const text = error instanceof Error ? error.message : "Settings could not be saved.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  const saveHotkeys = async () => {
    try {
      const response = await window.yaverVoice.settings.saveHotkeys({
        recording_trigger_mode: draft.recording_trigger_mode,
        push_to_talk_key: draft.push_to_talk_key,
        toggle_hotkey: draft.toggle_hotkey,
        translate_toggle_hotkey: draft.translate_toggle_hotkey
      });
      onSettings(response.config);
      setNotice(response.message);
      pushToast(response.message, response.success ? "success" : "error");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Hotkey save failed.");
      pushToast(error instanceof Error ? error.message : "Hotkey save failed.", "error");
    }
  };

  const prepareLocalModel = async () => {
    try {
      setNotice("Preparing local model...");
      await window.yaverVoice.settings.prepareLocalWhisperModel();
      const nextSettings = await window.yaverVoice.settings.get();
      onSettings(nextSettings);
      setNotice("Local model is ready.");
      pushToast("Local model is ready", "success");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Local model setup failed.");
      pushToast(error instanceof Error ? error.message : "Local model setup failed.", "error");
    }
  };

  const installRnnoiseModel = async () => {
    try {
      const response = await window.yaverVoice.settings.installRnnoiseModel();
      if (!response) return;
      onSettings(response.config);
      setDraft(response.config);
      setNotice(response.message);
      pushToast(response.message, "success");
    } catch (error) {
      const text = error instanceof Error ? error.message : "RNNoise model could not be imported.";
      setNotice(text);
      pushToast(text, "error");
    }
  };

  const confirmHotkeyCapture = () => {
    if (!hotkeyCapture || !capturedHotkey) {
      pushToast("Hotkey cannot be empty", "error");
      return;
    }
    if (hotkeyCapture === "push_to_talk") {
      setDraft({ ...draft, push_to_talk_key: capturedHotkey });
    } else if (hotkeyCapture === "toggle_recording") {
      setDraft({ ...draft, toggle_hotkey: capturedHotkey });
    } else {
      setDraft({ ...draft, translate_toggle_hotkey: capturedHotkey });
    }
    setHotkeyCapture(null);
    setCapturedHotkey("");
  };

  const selectedMicrophone = String(draft.input_device_index ?? -1);
  const providerIsLocal = draft.transcription_provider === "local";
  const localStatus = draft.local_whisper_status;
  const localStatusState = typeof localStatus?.status === "string" ? localStatus.status : "missing";
  const localReady = localStatusState === "ready" || localStatus?.transcription_ready === true;
  const localDependencyMissing = localStatus?.dependency_available === false;
  const localStatusMessage = typeof localStatus?.message === "string"
    ? localStatus.message
    : localReady
      ? "Local model is ready."
      : "Use Set up local mode before local transcription.";
  const localModelSource = localStatus?.model_source === "cache" ? "cache" : "app data";
  const apiKeyDisplayValue = apiKey || (!apiKeyEditing && draft.api_key_exists ? "**********" : "");
  const localInfo = localWhisperInfoCopy[localInfoLanguage];
  const audioCleanupStatus = draft.audio_cleanup_status;
  const rnnoiseReady = audioCleanupStatus?.rnnoise_ready === true;
  const arnndnAvailable = audioCleanupStatus?.arnndn_available === true;
  const rnnoiseMessage = audioCleanupStatus?.message ?? "RNNoise model missing. Noisy/Severe cleanup requires a .rnnn model.";
  const rnnoiseModesEnabled = rnnoiseReady && arnndnAvailable;
  const selectedAudioCleanupMode = !rnnoiseModesEnabled && (draft.audio_cleanup_mode === "noisy" || draft.audio_cleanup_mode === "severe")
    ? "normal"
    : draft.audio_cleanup_mode;
  const languageLabel = (value: string) => {
    const labels: Record<string, string> = {
      tr: "Turkish - Türkçe",
      en: "English",
      de: "German",
      fr: "French",
      es: "Spanish",
      it: "Italian",
      auto: "Auto"
    };
    return labels[value] ?? value;
  };

  const changeAndSave = (patch: Partial<Settings>, payload: Record<string, unknown>, toast: string) => {
    setDraft({ ...draft, ...patch });
    void savePartialSettings(payload, toast);
  };

  return (
    <>
      <section className="workspace settingsWorkspace" aria-labelledby="settings-title">
        <div className="workspaceHeader">
          <h2 id="settings-title">Settings</h2>
        </div>
        <div className="settingsLayout">
          <nav className="settingsCategoryNav" aria-label="Settings categories">
            {settingsCategories.map((category) => (
              <button
                aria-current={activeCategory === category.id ? "page" : undefined}
                className={activeCategory === category.id ? "active" : ""}
                key={category.id}
                onClick={() => setActiveCategory(category.id)}
                type="button"
              >
                {category.label}
              </button>
            ))}
          </nav>

          <div className="settingsContent">
            <section aria-labelledby="settings-transcription-title" className="settingsCategoryPanel" hidden={activeCategory !== "transcription"}>
              <div className="settingsCategoryHeader">
                <div><h3 id="settings-transcription-title">Transcription</h3><p>Choose the transcription workflow and language.</p></div>
                <button className="primaryButton" type="button" onClick={() => void saveSettings()}>Save changes</button>
              </div>

              <div className="settingsGroup">
                <span className="settingsGroupLabel">Provider</span>
                <div className="providerCards">
                  <button
                    aria-pressed={!providerIsLocal}
                    className={!providerIsLocal ? "providerChoice active" : "providerChoice"}
                    type="button"
                    onClick={() => changeAndSave({ transcription_provider: "groq" }, { transcription_provider: "groq" }, "Transcription engine updated")}
                  >
                    <span className="providerChoiceHeader">
                      <Cloud size={18} aria-hidden="true" />
                      <strong>Groq Cloud</strong>
                    </span>
                    <span>Cloud transcription with your API key.</span>
                    <small className="providerLocation">Selected audio is sent to Groq for transcription.</small>
                  </button>
                  <button
                    aria-pressed={providerIsLocal}
                    className={providerIsLocal ? "providerChoice active" : "providerChoice"}
                    type="button"
                    onClick={() => changeAndSave({ transcription_provider: "local" }, { transcription_provider: "local" }, "Transcription engine updated")}
                  >
                    <span className="providerChoiceHeader">
                      <HardDrive size={18} aria-hidden="true" />
                      <strong>Local Whisper</strong>
                    </span>
                    <span>On-device transcription using the prepared model.</span>
                    <small className="providerLocation">Audio is processed locally on this device.</small>
                  </button>
                </div>
              </div>

              {!providerIsLocal && (
                <div className="settingsGroup">
                  <label className="settingsField">
                    Groq API Key
                    <div className="settingsInline">
                      <input
                        value={apiKeyDisplayValue}
                        onFocus={() => setApiKeyEditing(true)}
                        onBlur={() => {
                          if (!apiKey) setApiKeyEditing(false);
                        }}
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          setApiKey(nextValue === "**********" ? "" : nextValue);
                        }}
                        placeholder="Enter new API key (gsk_...)"
                        type="password"
                      />
                      <button className="secondaryButton" type="button" onClick={() => void saveSettings()}>Update key</button>
                    </div>
                  </label>
                </div>
              )}

              <div className="settingsGroup fieldGrid">
                <label>
                  Transcription Language
                  <select value={draft.language} onChange={(event) => changeAndSave({ language: event.target.value }, { language: event.target.value }, "Language updated")}>
                    <option value="tr">{languageLabel("tr")}</option>
                    <option value="en">{languageLabel("en")}</option>
                    <option value="de">{languageLabel("de")}</option>
                    <option value="fr">{languageLabel("fr")}</option>
                    <option value="es">{languageLabel("es")}</option>
                    <option value="it">{languageLabel("it")}</option>
                    <option value="auto">{languageLabel("auto")}</option>
                  </select>
                </label>
                {providerIsLocal && (
                  <label>
                    Performance
                    <select value={draft.local_whisper_profile} onChange={(event) => changeAndSave({ local_whisper_profile: event.target.value }, { local_whisper_profile: event.target.value }, "Local profile updated")}>
                      <option value="fast">Fast</option>
                      <option value="balanced">Balanced</option>
                      <option value="quality">Quality Turbo</option>
                      <option value="high_quality">High Quality</option>
                    </select>
                  </label>
                )}
              </div>

              {providerIsLocal && (
                <div className="settingsGroup">
                  <div className="settingsSectionHeader">
                    <strong>Local Whisper</strong>
                    <button className="secondaryButton compactButton" type="button" onClick={() => setLocalInfoOpen(true)}>Info</button>
                  </div>
                  <div className="localStatusRow">
                    <p className={localReady ? "statusText successText" : localStatusState === "error" ? "statusText errorText" : "statusText"}>
                      {localReady ? "Ready" : localDependencyMissing ? "Package missing" : "Not ready"} - {localStatusMessage}
                    </p>
                    <button className="secondaryButton compactButton" type="button" onClick={() => void prepareLocalModel()} disabled={localReady}>
                      {localReady ? "Ready" : localDependencyMissing ? "Setup info" : "Set Up Local Mode"}
                    </button>
                  </div>
                  <button className="linkButton" type="button" onClick={() => setLocalAdvancedOpen((current) => !current)}>
                    {localAdvancedOpen ? "Hide advanced local settings" : "Advanced local settings"}
                  </button>
                  {localAdvancedOpen && (
                    <div className="advancedSettingsGrid">
                      <label>Device<select value={draft.local_whisper_device} onChange={(event) => changeAndSave({ local_whisper_device: event.target.value }, { local_whisper_device: event.target.value }, "Local device updated")}><option value="auto">Auto</option><option value="cpu">CPU</option><option value="cuda">NVIDIA GPU</option></select></label>
                      <label>Processing<select value={draft.local_whisper_compute_type} onChange={(event) => changeAndSave({ local_whisper_compute_type: event.target.value }, { local_whisper_compute_type: event.target.value }, "Local processing updated")}><option value="auto">Auto</option><option value="int8">Low memory</option><option value="float16">Fast GPU</option><option value="float32">Compatibility</option></select></label>
                      <label>CPU usage<select value={draft.local_whisper_cpu_usage} onChange={(event) => changeAndSave({ local_whisper_cpu_usage: event.target.value }, { local_whisper_cpu_usage: event.target.value }, "Local CPU usage updated")}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
                    </div>
                  )}
                </div>
              )}
            </section>

            <section aria-labelledby="settings-audio-title" className="settingsCategoryPanel" hidden={activeCategory !== "audio"}>
              <div className="settingsCategoryHeader">
                <div><h3 id="settings-audio-title">Audio</h3><p>Choose the input device and cleanup profile.</p></div>
                <button className="primaryButton" type="button" onClick={() => void saveSettings()}>Save changes</button>
              </div>
              {!rnnoiseReady && (
                <div className="rnnoiseBanner missing">
                  <div><strong>RNNoise model missing.</strong><span>{rnnoiseMessage}</span></div>
                  <div className="rnnoiseActions">
                    <button className="secondaryButton compactButton" type="button" onClick={() => setRnnoiseInfoOpen(true)}>Info</button>
                    <button className="secondaryButton compactButton" type="button" onClick={() => void installRnnoiseModel()}>Select .rnnn model</button>
                  </div>
                </div>
              )}
              {rnnoiseReady && (
                <div className="readinessRow"><div><strong>RNNoise</strong><span>Audio cleanup model is ready.</span></div><span className="installBadge"><Check size={12} /> Ready</span></div>
              )}
              <div className="settingsGroup fieldGrid">
                <label>
                  Microphone
                  <select value={selectedMicrophone} onChange={(event) => {
                    const nextIndex = Number(event.target.value);
                    const selected = microphones.find((mic) => mic.index === nextIndex);
                    changeAndSave({ input_device_index: nextIndex }, { input_device_index: nextIndex }, selected?.name?.includes("Bluetooth") ? "Bluetooth microphones may have low quality." : "Microphone updated");
                  }}>
                    <option value="-1">Default System Microphone</option>
                    {microphones.map((device) => <option key={device.index} value={device.index}>{device.name}</option>)}
                  </select>
                </label>
                <label>
                  <span><Wand2 size={15} /> Audio Cleanup</span>
                  <select value={selectedAudioCleanupMode} onChange={(event) => {
                    const audioCleanupMode = event.target.value as Settings["audio_cleanup_mode"];
                    changeAndSave({ audio_cleanup_mode: audioCleanupMode }, { audio_cleanup_mode: audioCleanupMode }, "Audio cleanup setting updated");
                  }}>
                    <option value="off">Off</option><option value="normal">Normal</option><option value="noisy" disabled={!rnnoiseModesEnabled}>Noisy</option><option value="severe" disabled={!rnnoiseModesEnabled}>Severe</option>
                  </select>
                </label>
              </div>
            </section>

            <section aria-labelledby="settings-behavior-title" className="settingsCategoryPanel" hidden={activeCategory !== "behavior"}>
              <div className="settingsCategoryHeader">
                <div><h3 id="settings-behavior-title">Behavior</h3><p>Control feedback and paste behavior.</p></div>
                <button className="primaryButton" type="button" onClick={() => void saveSettings()}>Save changes</button>
              </div>
              <div className="settingsGroup toggleList">
                <Toggle icon={Volume2} label="Sound" checked={draft.sound_enabled} onChange={(checked) => changeAndSave({ sound_enabled: checked }, { sound_enabled: checked }, "Sound setting updated")} />
                <Toggle icon={Clipboard} label="Auto-Paste" checked={draft.auto_paste_enabled} onChange={(checked) => changeAndSave({ auto_paste_enabled: checked }, { auto_paste_enabled: checked }, "Auto-paste setting updated")} />
                <Toggle icon={Clipboard} label="Toggle Auto-Paste" checked={draft.toggle_recording_auto_paste_enabled} onChange={(checked) => changeAndSave({ toggle_recording_auto_paste_enabled: checked }, { toggle_recording_auto_paste_enabled: checked }, "Toggle auto-paste setting updated")} />
                <Toggle icon={Languages} label="Translate EN" checked={draft.translate_enabled} onChange={(checked) => changeAndSave({ translate_enabled: checked }, { translate_enabled: checked }, "Translate setting updated")} />
                <label className="compactCheck"><input checked={draft.always_on_top} type="checkbox" onChange={(event) => changeAndSave({ always_on_top: event.target.checked }, { always_on_top: event.target.checked }, "Window behavior updated")} />Always on top</label>
              </div>
              <p className="settingsHint">Auto-Paste applies to dashboard and file workflows; Toggle Auto-Paste applies to Alt + R recordings.</p>
            </section>

            <section aria-labelledby="settings-hotkeys-title" className="settingsCategoryPanel" hidden={activeCategory !== "hotkeys"}>
              <div className="settingsCategoryHeader"><div><h3 id="settings-hotkeys-title">Hotkeys</h3><p>Set recording mode and keyboard shortcuts.</p></div></div>
              <div className="settingsGroup">
                <span className="settingsGroupLabel">Recording trigger</span>
                <div className="segmentControl">
                  <button className={draft.recording_trigger_mode === "hold_to_talk" ? "active" : ""} type="button" onClick={() => setDraft({ ...draft, recording_trigger_mode: "hold_to_talk" })}>Hold-to-talk</button>
                  <button className={draft.recording_trigger_mode === "toggle" ? "active" : ""} type="button" onClick={() => setDraft({ ...draft, recording_trigger_mode: "toggle" })}>Toggle</button>
                </div>
              </div>
              <div className="hotkeyRows">
                <div className="hotkeyCard"><span>Hold-to-talk</span><strong>{formatHotkeyDisplay(draft.push_to_talk_key)}</strong><button className="secondaryButton" type="button" onClick={() => setHotkeyCapture("push_to_talk")}>Change</button></div>
                <div className="hotkeyCard"><span>Toggle recording</span><strong>{formatHotkeyDisplay(draft.toggle_hotkey)}</strong><button className="secondaryButton" type="button" onClick={() => setHotkeyCapture("toggle_recording")}>Change</button></div>
                <div className="hotkeyCard"><span>Translate EN toggle</span><strong>{formatHotkeyDisplay(draft.translate_toggle_hotkey)}</strong><button className="secondaryButton" type="button" onClick={() => setHotkeyCapture("translate")}>Change</button></div>
              </div>
              {hotkeyCapture && (
                <div className="capturePanel">
                  <span>{capturedHotkey ? formatHotkeyDisplay(capturedHotkey) : "Press a key or combination"}</span>
                  <div className="buttonRow">
                    <button className="secondaryButton" type="button" onClick={() => { setHotkeyCapture(null); setCapturedHotkey(""); }}>Cancel</button>
                    <button className="primaryButton" type="button" onClick={confirmHotkeyCapture}>Confirm</button>
                  </div>
                </div>
              )}
              <div className="hotkeyFooter"><span>Ctrl + Alt + Q is reserved for quit.</span><button className="primaryButton" type="button" onClick={() => void saveHotkeys()}>Save Hotkeys</button></div>
            </section>

            <section aria-labelledby="settings-system-title" className="settingsCategoryPanel" hidden={activeCategory !== "system"}>
              <div className="settingsCategoryHeader"><div><h3 id="settings-system-title">System status</h3><p>Readiness for local media processing.</p></div></div>
              <div className="readinessList">
                <div className="readinessRow"><div><strong>FFmpeg</strong><span>Audio and video conversion dependency.</span></div><span className={ffmpegStatus?.installed ? "installBadge" : "installBadge missing"}>{ffmpegStatus?.installed ? "Ready" : "Missing"}</span></div>
                <div className="readinessRow"><div><strong>RNNoise</strong><span>{rnnoiseReady ? "Audio cleanup model is ready." : rnnoiseMessage}</span></div><span className={rnnoiseReady ? "installBadge" : "installBadge missing"}>{rnnoiseReady ? "Ready" : "Missing"}</span></div>
              </div>
            </section>
          </div>
        </div>

        {notice && <div className="settingsNotice" aria-live="polite"><span className="notice">{notice}</span></div>}
      </section>
      {localInfoOpen && (
        <LocalWhisperInfoDialog
          info={localInfo}
          language={localInfoLanguage}
          onLanguageChange={setLocalInfoLanguage}
          onClose={() => setLocalInfoOpen(false)}
        />
      )}
      {rnnoiseInfoOpen && (
        <RnnoiseInfoDialog
          managedModelDir={audioCleanupStatus?.managed_model_dir}
          onClose={() => setRnnoiseInfoOpen(false)}
        />
      )}
    </>
  );
}
