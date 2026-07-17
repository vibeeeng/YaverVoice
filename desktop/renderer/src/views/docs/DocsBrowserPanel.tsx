import { FileText, FolderOpen, RefreshCcw, X } from "lucide-react";

export function DocsBrowserPanel({
  directory,
  directoryToken,
  directoryLoading,
  files,
  previewPath,
  previewContent,
  previewOpen,
  previewLoading,
  onSelectDirectory,
  onRefreshDirectory,
  onOpenPreview,
  onClosePreview
}: {
  directory: string | null;
  directoryToken: string | null;
  directoryLoading: boolean;
  files: Array<{ name: string; path: string }>;
  previewPath: string | null;
  previewContent: string | null;
  previewOpen: boolean;
  previewLoading: boolean;
  onSelectDirectory: () => void;
  onRefreshDirectory: () => void;
  onOpenPreview: (path: string) => void;
  onClosePreview: () => void;
}) {
  return (
    <>
      <div className="docsBrowserSection fileWorkflowSubsection">
        <div className="docsBrowserHeader">
          <span className="docsBrowserTitle">Preview</span>
          <button className="secondaryButton" type="button" onClick={onSelectDirectory}>
            <FolderOpen size={14} />
            {directory ? "Change folder" : "Select folder"}
          </button>
          {directory && directoryToken && (
            <button className="iconButton" type="button" onClick={onRefreshDirectory} title="Refresh">
              <RefreshCcw size={13} />
            </button>
          )}
        </div>
        {directory && (
          <span className="docsDirPath">{directory}</span>
        )}
        {directoryLoading && <span className="statusText">Loading...</span>}
        {files.length > 0 && (
          <div className="docsFileList">
            {files.map((file) => (
              <button
                key={file.path}
                className={`docsFileItem ${previewPath === file.path ? "active" : ""}`}
                type="button"
                onClick={() => onOpenPreview(file.path)}
              >
                <FileText size={13} />
                <span>{file.name}</span>
              </button>
            ))}
          </div>
        )}
        {directory && files.length === 0 && !directoryLoading && (
          <span className="statusText">No markdown files found.</span>
        )}
      </div>
      {previewPath && previewOpen && (
        <div className="docsPreviewPanel open">
          <button
            className="docsPreviewToggle"
            type="button"
            onClick={onClosePreview}
          >
            <FileText size={14} />
            <span>{previewPath.split(/[/\\]/).pop()}</span>
            {previewLoading && <span className="statusText">Loading...</span>}
            <X size={13} />
          </button>
          {previewContent && (
            <pre className="docsPreviewContent">{previewContent}</pre>
          )}
        </div>
      )}
    </>
  );
}
