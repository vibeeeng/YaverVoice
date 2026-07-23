import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";

import type { ToastMessage } from "../types/ui";

const toastIcons = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: TriangleAlert,
  info: Info
};

export function ToastViewport({ toasts }: { toasts: ToastMessage[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="toastViewport">
      {toasts.map((toast) => {
        const Icon = toastIcons[toast.type];
        return (
          <div className={`toast ${toast.type}`} key={toast.id} role="status">
            <Icon size={16} aria-hidden="true" />
            <span>{toast.message}</span>
          </div>
        );
      })}
    </div>
  );
}
