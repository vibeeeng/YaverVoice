import { useMemo } from "react";
import { FileAudio, FileText, History, Mic, Sparkles, Wand2 } from "lucide-react";

import type { HistoryItem, Settings } from "../types/yaverVoice";
import type { SectionId } from "../types/ui";

export function HomeView({
  settings,
  history,
  onNavigate
}: {
  settings: Settings | null;
  history: HistoryItem[];
  onNavigate: (section: SectionId) => void;
}) {
  const stats = useMemo(
    () => [
      { label: "Provider", value: settings?.transcription_provider === "local" ? "Local Whisper" : "Groq Cloud" },
      { label: "Language", value: settings?.language?.toUpperCase() ?? "TR" },
      { label: "History", value: String(history.length) },
      { label: "Translate EN", value: settings?.translate_enabled ? "On" : "Off" }
    ],
    [settings, history.length]
  );

  return (
    <div className="homeLayout">
      <section className="homeHero" aria-label="YaverVoice status">
        <div className="heroCopy">
          <h2>YaverVoice</h2>
        </div>
        <div className="heroActions">
          <button className="primaryButton" type="button" onClick={() => onNavigate("record")}>
            <Mic size={16} />
            Record
          </button>
          <button className="secondaryButton" type="button" onClick={() => onNavigate("files")}>
            <FileAudio size={16} />
            File
          </button>
          <button className="secondaryButton" type="button" onClick={() => onNavigate("history")}>
            <History size={16} />
            History
          </button>
          <button className="secondaryButton" type="button" onClick={() => onNavigate("docs")}>
            <FileText size={16} />
            Docs
          </button>
          <button className="secondaryButton" type="button" onClick={() => onNavigate("converter")}>
            <Wand2 size={16} />
            Converter
          </button>
          <button className="secondaryButton" type="button" onClick={() => onNavigate("quick")}>
            <Sparkles size={16} />
            Quick Dictation
          </button>
        </div>
      </section>
      <div className="metricRow">
        {stats.map((stat) => (
          <div className="metric" key={stat.label}>
            <span>{stat.label}</span>
            <strong>{stat.value}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}
