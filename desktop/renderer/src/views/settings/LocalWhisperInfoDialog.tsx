import { Info, X } from "lucide-react";

import type { LocalInfoLanguage } from "../../types/ui";
import type { LocalInfoCopy } from "./localWhisperInfo";

export function LocalWhisperInfoDialog({
  info,
  language,
  onLanguageChange,
  onClose
}: {
  info: LocalInfoCopy;
  language: LocalInfoLanguage;
  onLanguageChange: (language: LocalInfoLanguage) => void;
  onClose: () => void;
}) {
  return (
    <div className="modalBackdrop" role="presentation" onClick={onClose}>
      <section className="localInfoDialog" aria-labelledby="local-info-title" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="localInfoHeader">
          <div className="localInfoTitle">
            <span className="infoIcon"><Info size={18} /></span>
            <div>
              <h3 id="local-info-title">{info.title}</h3>
              <p>{info.subtitle}</p>
            </div>
          </div>
          <div className="localInfoControls">
            <select value={language} onChange={(event) => onLanguageChange(event.target.value as LocalInfoLanguage)}>
              <option value="tr">Türkçe</option>
              <option value="en">English</option>
            </select>
            <button className="iconButton" type="button" onClick={onClose} aria-label={info.close}>
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="localInfoContent">
          {info.sections.map(([title, body]) => (
            <div className="infoBlock" key={title}>
              <strong>{title}</strong>
              <p>{body}</p>
            </div>
          ))}

          <div className="infoSectionTitle">{info.profileTitle}</div>
          <div className="profileInfoList">
            {info.profiles.map((profile) => (
              <div className="profileInfoCard" key={profile.name}>
                <div className="profileInfoTop">
                  <strong>{profile.name}</strong>
                  <span>Model: {profile.model}</span>
                </div>
                <div className="profileInfoMeta">
                  <span>{profile.disk}</span>
                  <span>{profile.memory}</span>
                  <span>{profile.gpu}</span>
                </div>
                <p>{profile.note}</p>
              </div>
            ))}
          </div>

          <div className="infoSectionTitle">{info.advancedTitle}</div>
          <div className="advancedInfoGrid">
            {info.advanced.map(([title, body]) => (
              <div className="advancedInfoCard" key={title}>
                <strong>{title}</strong>
                <p>{body}</p>
              </div>
            ))}
          </div>

          <div className="recommendationBox">{info.recommendation}</div>
        </div>

        <div className="localInfoFooter">
          <button className="primaryButton" type="button" onClick={onClose}>{info.close}</button>
        </div>
      </section>
    </div>
  );
}
