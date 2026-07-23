import { Info, X } from "lucide-react";

import { ModalSurface } from "../../components/ModalSurface";

export function RnnoiseInfoDialog({
  managedModelDir,
  onClose
}: {
  managedModelDir?: string | null;
  onClose: () => void;
}) {
  return (
    <ModalSurface labelledBy="rnnoise-info-title" className="localInfoDialog rnnoiseInfoDialog" onClose={onClose} closeOnBackdrop>
        <div className="localInfoHeader">
          <div className="localInfoTitle">
            <span className="infoIcon"><Info size={18} /></span>
            <div>
              <h3 id="rnnoise-info-title">RNNoise Audio Cleanup</h3>
              <p>Noisy and Severe use an FFmpeg RNNoise filter with a local .rnnn model.</p>
            </div>
          </div>
          <button className="iconButton" type="button" onClick={onClose} aria-label="Close RNNoise info">
            <X size={16} />
          </button>
        </div>
        <div className="localInfoContent">
          <div className="infoBlock">
            <strong>What it does</strong>
            <p>RNNoise reduces steady background noise before transcription. It can help with fans, room noise, and compressed microphone audio.</p>
          </div>
          <div className="infoBlock">
            <strong>Normal vs Noisy/Severe</strong>
            <p>Normal uses basic FFmpeg high-pass, low-pass, and loudness normalization. Noisy and Severe require RNNoise and can change speech more aggressively.</p>
          </div>
          <div className="infoBlock">
            <strong>Risk</strong>
            <p>A stronger cleanup mode can remove quiet speech or distort words on already clean audio. Use Off or Normal when the source is clear.</p>
          </div>
          <div className="infoBlock">
            <strong>Install a model manually</strong>
            <p>Select a .rnnn model that you obtained from a source whose license and integrity you trust. YaverVoice copies it to app data and does not download a model automatically.</p>
          </div>
          <div className="recommendationBox">
            Managed folder: {managedModelDir ?? "not available"}
          </div>
        </div>
        <div className="localInfoFooter">
          <button className="primaryButton" type="button" onClick={onClose}>Close</button>
        </div>
    </ModalSurface>
  );
}
