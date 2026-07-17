import type { DocsDetailProfile, DocsModelProfile } from "../../types/yaverVoice";
import type { DocsOutputLanguage } from "../../types/ui";

export type DocsOutputLanguageOption = {
  id: DocsOutputLanguage;
  label: string;
};

export function DocsOptionsPanel({
  models,
  details,
  outputLanguages,
  selectedModel,
  selectedDetail,
  selectedOutputLanguage,
  processing,
  onModelChange,
  onDetailChange,
  onOutputLanguageChange
}: {
  models: DocsModelProfile[];
  details: DocsDetailProfile[];
  outputLanguages: DocsOutputLanguageOption[];
  selectedModel: string;
  selectedDetail: string;
  selectedOutputLanguage: DocsOutputLanguage;
  processing: boolean;
  onModelChange: (model: string) => void;
  onDetailChange: (detail: string) => void;
  onOutputLanguageChange: (language: DocsOutputLanguage) => void;
}) {
  return (
    <div className="fieldGrid">
      <label>
        Model
        <select value={selectedModel} onChange={(event) => onModelChange(event.target.value)} disabled={processing || models.length === 0}>
          {models.map((model) => (
            <option value={model.id} key={model.id}>
              {model.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Detail
        <select value={selectedDetail} onChange={(event) => onDetailChange(event.target.value)} disabled={processing || details.length === 0}>
          {details.map((detail) => (
            <option value={detail.id} key={detail.id}>
              {detail.label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Output Language
        <select
          value={selectedOutputLanguage}
          onChange={(event) => onOutputLanguageChange(event.target.value as DocsOutputLanguage)}
          disabled={processing}
        >
          {outputLanguages.map((language) => (
            <option value={language.id} key={language.id}>
              {language.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
