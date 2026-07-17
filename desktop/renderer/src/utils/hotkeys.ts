export function hotkeyFromKeyboardEvent(event: KeyboardEvent, singleKeyOnly: boolean) {
  if (singleKeyOnly) {
    return normalizeSingleKeyFromEvent(event);
  }
  const key = event.key;
  const parts: string[] = [];
  if (event.ctrlKey || key === "Control") parts.push("<ctrl>");
  if (event.altKey || key === "Alt") parts.push("<alt>");
  if (event.shiftKey || key === "Shift") parts.push("<shift>");
  if (event.metaKey || key === "Meta") parts.push("<cmd>");

  const mainKey = normalizeSingleKeyFromEvent(event);
  if (mainKey && !["left_ctrl", "right_ctrl", "left_alt", "right_alt", "left_shift", "right_shift"].includes(mainKey)) {
    parts.push(mainKey);
  } else if (parts.length === 0 && mainKey) {
    return mainKey.replace("left_", "").replace("right_", "");
  }
  return parts.join("+");
}

export function normalizeSingleKeyFromEvent(event: KeyboardEvent) {
  const key = event.key;
  if (key === "Control") return event.location === KeyboardEvent.DOM_KEY_LOCATION_RIGHT ? "right_ctrl" : "left_ctrl";
  if (key === "Alt") return event.location === KeyboardEvent.DOM_KEY_LOCATION_RIGHT ? "right_alt" : "left_alt";
  if (key === "Shift") return event.location === KeyboardEvent.DOM_KEY_LOCATION_RIGHT ? "right_shift" : "left_shift";
  if (key === " ") return "space";
  if (key === "Escape") return "esc";
  if (key === "Enter") return "enter";
  if (key === "Tab") return "tab";
  if (key && key.length === 1) return key.toLowerCase();
  return key ? key.toLowerCase() : "";
}

export function formatHotkeyDisplay(value: string) {
  if (!value) return "Not set";
  const labels: Record<string, string> = {
    "<ctrl>": "Ctrl",
    "<alt>": "Alt",
    "<shift>": "Shift",
    "<cmd>": "Cmd",
    ctrl: "Ctrl",
    alt: "Alt",
    shift: "Shift",
    left_ctrl: "Left Ctrl",
    right_ctrl: "Right Ctrl",
    left_alt: "Left Alt",
    right_alt: "Right Alt",
    left_shift: "Left Shift",
    right_shift: "Right Shift",
    space: "Space",
    enter: "Enter",
    tab: "Tab",
    esc: "Esc"
  };
  return value.split("+").map((part) => {
    const normalized = part.trim().toLowerCase();
    return labels[normalized] ?? (normalized.length === 1 ? normalized.toUpperCase() : normalized.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()));
  }).join(" + ");
}
