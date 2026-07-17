import { FileAudio, History, Mic, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { WorkspaceId } from "../types/ui";

export const workspaces: Array<{ id: WorkspaceId; label: string; icon: LucideIcon }> = [
  { id: "capture", label: "Capture", icon: Mic },
  { id: "files", label: "Files", icon: FileAudio },
  { id: "library", label: "Library", icon: History },
  { id: "settings", label: "Settings", icon: Settings }
];
