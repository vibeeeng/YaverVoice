import { useEffect, useMemo, useState } from "react";
import { Link as LinkIcon, Lock, Trash2, Unlock } from "lucide-react";

import type { HistoryItem } from "../types/yaverVoice";
import type { ToastMessage } from "../types/ui";

export function HistoryView({
  editUnlocked,
  onEditUnlocked,
  history,
  onHistory,
  onOpenCapture,
  onOpenFiles,
  pushToast
}: {
  editUnlocked: boolean;
  onEditUnlocked: (unlocked: boolean) => void;
  history: HistoryItem[];
  onHistory: (items: HistoryItem[]) => void;
  onOpenCapture?: () => void;
  onOpenFiles?: () => void;
  pushToast: (message: string, type?: ToastMessage["type"]) => void;
}) {
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  useEffect(() => {
    setEditing((current) => {
      const next: Record<string, string> = {};
      history.forEach((item) => {
        if (current[item.id] !== undefined) {
          next[item.id] = current[item.id];
        }
      });
      return next;
    });
    setSelected((current) => current.filter((id) => history.some((item) => item.id === id)));
  }, [history]);

  const clearHistory = async () => {
    const response = await window.yaverVoice.history.clear();
    onHistory(response.history);
    setSelected([]);
    pushToast("History cleared", "info");
  };

  const createMerged = async () => {
    const selectedItems = selected.map((id) => history.find((item) => item.id === id)).filter((item): item is HistoryItem => Boolean(item));
    const text = selectedItems.map((item) => (editing[item.id] ?? item.text).trim()).filter(Boolean).join(" ");
    if (!text) {
      return;
    }
    const response = await window.yaverVoice.history.createMerged(text);
    onHistory(response.history);
    setSelected([]);
    pushToast(`Merged ${selectedItems.length} items in order`, "success");
  };

  const deleteSelected = async () => {
    if (selected.length === 0) {
      return;
    }
    let nextHistory = history;
    for (const id of selected) {
      const response = await window.yaverVoice.history.delete(id);
      nextHistory = response.history;
    }
    onHistory(nextHistory);
    pushToast(`Deleted ${selected.length} items`, "info");
    setSelected([]);
  };

  const toggleSelected = (id: string, checked: boolean) => {
    setSelected((current) => {
      if (checked && !current.includes(id)) {
        return [...current, id];
      }
      return current.filter((item) => item !== id);
    });
  };

  const toggleSelectAll = (checked: boolean) => {
    setSelected(checked ? history.map((item) => item.id) : []);
  };

  const saveEditedText = async (item: HistoryItem) => {
    if (!editUnlocked) {
      return;
    }
    const nextText = editing[item.id] ?? item.text;
    if (nextText === item.text || !nextText.trim()) {
      return;
    }
    const response = await window.yaverVoice.history.updateText(item.id, nextText);
    onHistory(response.history);
    pushToast("Transcript saved", "success");
  };

  const allSelected = history.length > 0 && selected.length === history.length;
  const someSelected = selected.length > 0 && selected.length < history.length;
  const resizeTextarea = (element: HTMLTextAreaElement | null) => {
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  };

  return (
    <section className="workspace libraryWorkspace historyLayout" aria-labelledby="library-title">
      <div className="workspaceHeader libraryHeader">
        <div>
          <span className="eyebrow">CURRENT SESSION</span>
          <h2 id="library-title">Library</h2>
          <div className="librarySummary">
            <span>{history.length} {history.length === 1 ? "transcript" : "transcripts"}</span>
            <span>{editUnlocked ? "Editing unlocked" : "Editing locked"}</span>
            {selected.length > 0 && <span className="selectedCount">{selected.length} selected</span>}
          </div>
        </div>
        <div className="historyHeaderActions">
          {history.length > 0 && (
            <label className="selectAllControl">
              <input
                aria-label="Select all history"
                checked={allSelected}
                ref={(element) => {
                  if (element) element.indeterminate = someSelected;
                }}
                type="checkbox"
                onChange={(event) => toggleSelectAll(event.target.checked)}
              />
              Select all
            </label>
          )}
          <button
            className={editUnlocked ? "lockButton unlocked" : "lockButton"}
            type="button"
            onClick={() => {
              const next = !editUnlocked;
              onEditUnlocked(next);
              pushToast(next ? "Edit mode enabled" : "Edit mode disabled", "info");
            }}
            title={editUnlocked ? "Lock transcript editing" : "Unlock transcript editing"}
          >
            {editUnlocked ? <Unlock size={16} /> : <Lock size={16} />}
            {editUnlocked ? "Edit ON" : "Locked"}
          </button>
          {history.length > 0 && (
            <button className="clearHistoryButton" type="button" onClick={() => void clearHistory()}>
              Clear All
            </button>
          )}
        </div>
      </div>

      {selected.length > 0 && (
        <div className="bulkActionsBar">
          <button className="primaryButton" type="button" onClick={() => void createMerged()}>
            <LinkIcon size={15} />
            Merge
          </button>
          <button className="dangerButton" type="button" onClick={() => void deleteSelected()}>
            <Trash2 size={15} />
            Delete Selected
          </button>
        </div>
      )}

      {history.length === 0 ? (
        <div className="emptyState libraryEmptyState">
          <div>
            <h3>No transcripts in this session</h3>
            <p>Start a capture or process a file to add transcripts here.</p>
          </div>
          <div className="emptyStateActions">
            {onOpenCapture && <button className="secondaryButton" type="button" onClick={onOpenCapture}>Open Capture</button>}
            {onOpenFiles && <button className="secondaryButton" type="button" onClick={onOpenFiles}>Open Files</button>}
          </div>
        </div>
      ) : (
        <div className="historyList">
          {history.map((item) => {
            const editValue = editing[item.id] ?? item.text;
            const isSelected = selectedSet.has(item.id);
            const selectedIndex = isSelected ? selected.indexOf(item.id) : -1;
            const wordCount = item.text.trim() ? item.text.trim().split(/\s+/).length : 0;
            const isLong = wordCount >= 100;
            const isExpanded = expanded[item.id] === true || editUnlocked || !isLong;
            const toggleExpanded = () => {
              if (editUnlocked || !isLong) {
                return;
              }
              setExpanded((current) => ({ ...current, [item.id]: current[item.id] !== true }));
            };
            return (
              <article className={isSelected ? "historyItem selected" : "historyItem"} key={item.id}>
                <div className="historyItemRow">
                  <input
                    aria-label={`Select transcript from ${item.timestamp}`}
                    className="itemCheckbox"
                    type="checkbox"
                    checked={isSelected}
                    onChange={(event) => toggleSelected(item.id, event.target.checked)}
                  />
                  <div className="historyItemBody">
                    <div className="historyItemHeader">
                      <div className="historyMeta">
                        {item.is_split && item.chunk_part ? <span className="chunkBadge">Parça {item.chunk_part}</span> : null}
                        <strong>{item.timestamp}</strong>
                      </div>
                      <div className="historyActions">
                        {isSelected && <span className="orderBadge">{selectedIndex + 1}</span>}
                        <button className="textAction" type="button" onClick={() => void window.yaverVoice.clipboard.copy(editValue).then(() => pushToast("Copied to clipboard", "success"))}>
                          Copy
                        </button>
                        <button
                          className="textAction"
                          type="button"
                          onClick={() => void window.yaverVoice.files.saveTranscript(editValue, `transcript_${new Date().toISOString().slice(0, 10)}.txt`).then((saved) => {
                            if (saved.success) pushToast("Kaydedildi", "success");
                          })}
                        >
                          Download
                        </button>
                      </div>
                    </div>

                    {editUnlocked ? (
                      <div className="expandedTranscript">
                        <textarea
                          ref={resizeTextarea}
                          value={editValue}
                          onBlur={() => void saveEditedText(item)}
                          onClick={(event) => event.stopPropagation()}
                          onInput={(event) => resizeTextarea(event.currentTarget)}
                          onChange={(event) => setEditing({ ...editing, [item.id]: event.target.value })}
                        />
                      </div>
                    ) : isLong ? (
                      <button
                        className="readonlyTranscript canCollapse"
                        type="button"
                        onClick={toggleExpanded}
                      >
                        <span className={isExpanded ? "readonlyTranscriptText expandedTranscriptText" : "readonlyTranscriptText collapsedTranscriptText"}>
                          {editValue}
                        </span>
                        <small>{isExpanded ? `Küçültmek için tıklayın (${wordCount} kelime)` : `Devamını görmek için tıklayın (${wordCount} kelime)`}</small>
                      </button>
                    ) : (
                      <div className="readonlyTranscript">
                        <span className="readonlyTranscriptText">{editValue}</span>
                      </div>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
