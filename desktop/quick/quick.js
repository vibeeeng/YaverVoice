const bubble = document.getElementById("bubble");
const recordButton = document.getElementById("recordButton");
const title = document.getElementById("title");
const status = document.getElementById("status");
const spinner = document.getElementById("spinner");
const usesNativeWindowDrag = window.yaverVoice?.platform === "linux";
const dragState = { active: false, moved: false, pointerId: null, startedOnRecord: false, startX: 0, startY: 0, lastX: 0, lastY: 0 };
let suppressNextClick = false;
let toggleInFlight = false;
let currentStatus = { recording: false, transcribing: false, mode: "standard" };
const stateCopy = {
  idle: ["YaverVoice", "Ready"], starting: ["Starting", "Wait"], recording: ["Listening", "Speak"],
  stopping: ["Stopping", "Wait"], processing: ["Processing", "Wait"], success: ["Done", "Copied"], error: ["Failed", "Retry"]
};

if (usesNativeWindowDrag) bubble.classList.add("platform-linux");

function renderState(state) {
  bubble.className = `bubble ${usesNativeWindowDrag ? "platform-linux " : ""}${state === "idle" ? "" : state}`.trim();
  spinner.hidden = !["starting", "stopping", "processing"].includes(state);
  const copy = stateCopy[state];
  if (copy) [title.textContent, status.textContent] = copy;
}

function setRecordingState(payload) {
  if (payload) currentStatus = { recording: Boolean(payload.recording), transcribing: Boolean(payload.transcribing), mode: typeof payload.mode === "string" ? payload.mode : "standard" };
  if (payload?.recording) return renderState("recording");
  if (payload?.transcribing) return renderState("processing");
  renderState("idle");
}

bubble.addEventListener("pointerdown", (event) => {
  if (usesNativeWindowDrag || event.button !== 0 || !window.yaverVoice || event.target.closest(".actions")) return;
  Object.assign(dragState, { active: true, moved: false, pointerId: event.pointerId, startedOnRecord: recordButton.contains(event.target), startX: event.screenX, startY: event.screenY, lastX: event.screenX, lastY: event.screenY });
  bubble.setPointerCapture(event.pointerId);
});

bubble.addEventListener("pointermove", (event) => {
  if (!dragState.active || dragState.pointerId !== event.pointerId || !window.yaverVoice) return;
  const totalX = event.screenX - dragState.startX;
  const totalY = event.screenY - dragState.startY;
  const deltaX = event.screenX - dragState.lastX;
  const deltaY = event.screenY - dragState.lastY;
  dragState.lastX = event.screenX;
  dragState.lastY = event.screenY;
  if (!dragState.moved && Math.hypot(totalX, totalY) < 4) return;
  dragState.moved = true;
  suppressNextClick = dragState.startedOnRecord;
  bubble.classList.add("dragging");
  void window.yaverVoice.quick.moveWindowBy(deltaX, deltaY);
});

function finishDrag(event) {
  if (!dragState.active || dragState.pointerId !== event.pointerId) return;
  dragState.active = false;
  dragState.pointerId = null;
  dragState.startedOnRecord = false;
  bubble.classList.remove("dragging");
  if (bubble.hasPointerCapture(event.pointerId)) bubble.releasePointerCapture(event.pointerId);
}
bubble.addEventListener("pointerup", finishDrag);
bubble.addEventListener("pointercancel", finishDrag);

recordButton.addEventListener("click", async () => {
  if (suppressNextClick) { suppressNextClick = false; return; }
  if (!window.yaverVoice || toggleInFlight) return;
  toggleInFlight = true;
  renderState(currentStatus.recording ? "stopping" : "starting");
  try { setRecordingState(await window.yaverVoice.quick.toggleRecording()); }
  catch (error) { renderState("error"); status.textContent = error?.message || "Retry"; }
  finally { toggleInFlight = false; }
});

document.getElementById("showButton").addEventListener("click", () => window.yaverVoice?.quick.showDashboard());
document.getElementById("hideButton").addEventListener("click", () => window.yaverVoice?.quick.hideWindow());

if (window.yaverVoice) {
  window.yaverVoice.recording.status().then(setRecordingState).catch(() => renderState("idle"));
  window.yaverVoice.onSidecarEvent((event) => {
    if (event.method === "recording.state") setRecordingState(event.params);
    if (event.method === "quick.status" && typeof event.params?.state === "string") renderState(event.params.state);
    if (event.method === "quick.status" && typeof event.params?.message === "string") status.textContent = event.params.message;
  });
}
