import { useEffect, useState } from "react";
import { Mic, Square } from "lucide-react";

import type { RecordingStatus, Settings } from "../types/yaverVoice";
import type { ToastMessage } from "../types/ui";

export function RecordView({
  status,
  onStatus,
  settings,
  pushToast
}: {
  status: RecordingStatus;
  onStatus: (status: RecordingStatus) => void;
  settings: Settings | null;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [notice, setNotice] = useState("");
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!status.recording) {
      setSeconds(0);
      return undefined;
    }
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 250);
    return () => window.clearInterval(timer);
  }, [status.recording]);

  const toggle = async () => {
    try {
      const next = await window.yaverVoice.recording.toggle();
      onStatus(next);
      const text = next.recording ? "Recording started." : next.transcribing ? "Transcribing..." : "Recording stopped.";
      setNotice(text);
      pushToast(text, "info");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Recording failed.");
      pushToast(error instanceof Error ? error.message : "Recording failed.", "error");
    }
  };
  const timerLabel = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  return (
    <div className="captureActionSurface">
      <div className="recordStatus" aria-live="polite">
        <span className={status.recording ? "liveDot on" : "liveDot"} />
        <strong>{status.recording ? "Recording" : status.transcribing ? "Transcribing" : "Ready"}</strong>
        <span>{status.recording ? timerLabel : "00:00"}</span>
      </div>
      <button className={status.recording ? "recordButton stop" : "recordButton"} type="button" onClick={() => void toggle()} disabled={status.transcribing}>
        {status.recording ? <Square size={22} /> : <Mic size={24} />}
        {status.recording ? "Stop" : "Record"}
      </button>
      <div className="hotkeyBadge">{settings?.push_to_talk_key_display ?? "Right Ctrl"} (Hold)</div>
      {notice && <p className="statusText">{notice}</p>}
    </div>
  );
}
