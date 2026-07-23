import { useEffect, useRef, type ReactNode, type RefObject } from "react";

const focusableSelector = [
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "a[href]",
  '[tabindex]:not([tabindex="-1"])'
].join(",");

export function ModalSurface({
  labelledBy,
  className,
  onClose,
  closeOnBackdrop = false,
  returnFocusFallbackRef,
  children
}: {
  labelledBy: string;
  className: string;
  onClose: () => void;
  closeOnBackdrop?: boolean;
  returnFocusFallbackRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  const dialogRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const openerRef = useRef<HTMLElement | null>(null);
  const returnFrameRef = useRef<number | null>(null);
  onCloseRef.current = onClose;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return undefined;

    if (returnFrameRef.current !== null) {
      cancelAnimationFrame(returnFrameRef.current);
      returnFrameRef.current = null;
    }
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement && !dialog.contains(activeElement)) {
      openerRef.current = activeElement;
    }

    const focusable = () => Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector));
    (focusable()[0] ?? dialog).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const items = focusable();
      if (items.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    dialog.addEventListener("keydown", handleKeyDown);
    return () => {
      dialog.removeEventListener("keydown", handleKeyDown);
      returnFrameRef.current = requestAnimationFrame(() => {
        returnFrameRef.current = null;
        const opener = openerRef.current;
        if (opener?.isConnected && !opener.matches(":disabled")) {
          opener.focus();
          return;
        }
        const fallback = returnFocusFallbackRef?.current;
        if (fallback?.isConnected) fallback.focus();
      });
    };
  }, []);

  return (
    <div
      className="modalBackdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (closeOnBackdrop && event.target === event.currentTarget) onCloseRef.current();
      }}
    >
      <section
        ref={dialogRef}
        className={className}
        aria-labelledby={labelledBy}
        aria-modal="true"
        role="dialog"
        tabIndex={-1}
      >
        {children}
      </section>
    </div>
  );
}
