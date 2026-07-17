import { useState } from "react";
import { Mic, Sparkles } from "lucide-react";

import type { RecordingStatus } from "../types/yaverVoice";
import type { ToastMessage } from "../types/ui";

export function QuickDictationView({
  status,
  onStatus,
  pushToast
}: {
  status: RecordingStatus;
  onStatus: (status: RecordingStatus) => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [notice, setNotice] = useState("");
  const [bubbleVisible, setBubbleVisible] = useState(false);
  const toggle = async () => {
    try {
      const next = await window.yaverVoice.quick.toggleRecording();
      onStatus(next);
      const text = next.recording ? "Quick Dictation recording." : "Quick Dictation stopped.";
      setNotice(text);
      pushToast(text, "info");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Quick Dictation failed.");
      pushToast(error instanceof Error ? error.message : "Quick Dictation failed.", "error");
    }
  };

  const toggleBubble = async () => {
    try {
      const result = await window.yaverVoice.quick.toggleWindow();
      setBubbleVisible(result.visible);
      pushToast(result.visible ? "Quick Dictation bubble shown" : "Quick Dictation bubble hidden", "info");
    } catch (error) {
      pushToast(error instanceof Error ? error.message : "Quick Dictation bubble failed.", "error");
    }
  };

  return (
    <div className="captureActionSurface">
      <div className="recordStatus" aria-live="polite">
        <span className={status.mode === "bubble" && status.recording ? "liveDot on" : "liveDot"} />
        <strong>{status.mode === "bubble" && status.recording ? "Recording" : status.transcribing ? "Processing" : "Ready"}</strong>
      </div>
      <button className={status.recording ? "recordButton stop" : "recordButton"} type="button" onClick={() => void toggle()} disabled={status.transcribing && !status.recording}>
        <Mic size={24} />
        {status.recording ? "Stop" : "Record"}
      </button>
      <div className="captureSecondaryAction">
        <button className="secondaryButton" type="button" onClick={() => void toggleBubble()}>
          <Sparkles size={16} />
          {bubbleVisible ? "Hide Bubble" : "Show Bubble"}
        </button>
      </div>
      {notice && <p className="statusText">{notice}</p>}
    </div>
  );
}
