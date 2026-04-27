import { X } from "lucide-react";
import {
  type ReactNode,
  useEffect,
} from "react";

import { cn } from "../../utils/cn";

type ModalSize =
  | "md"
  | "lg"
  | "xl";

const SIZE_CLASS: Record<
  ModalSize,
  string
> = {
  md: "max-w-md",
  lg: "max-w-2xl",
  xl: "max-w-5xl",
};

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  eyebrow?: string;
  className?: string;
  size?: ModalSize;
  headerClassName?: string;
  bodyClassName?: string;
  titleClassName?: string;
  eyebrowClassName?: string;
  closeButtonClassName?: string;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  eyebrow = "Route configuration",
  className,
  size = "lg",
  headerClassName,
  bodyClassName,
  titleClassName,
  eyebrowClassName,
  closeButtonClassName,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;

    const handler = (
      e: KeyboardEvent
    ) => {
      if (e.key === "Escape")
        onClose();
    };

    document.addEventListener(
      "keydown",
      handler
    );

    document.body.style.overflow =
      "hidden";

    return () => {
      document.removeEventListener(
        "keydown",
        handler
      );

      document.body.style.overflow =
        "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close modal"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/55 backdrop-blur-sm"
      />

      {/* Panel */}
      <div
        className={cn(
          "relative z-10 flex w-full flex-col overflow-hidden rounded-[32px] border border-slate-200/90 bg-white shadow-[0_32px_120px_-52px_rgba(15,23,42,0.7)]",
          "max-h-[92vh]",
          SIZE_CLASS[size],
          className
        )}
      >
        {/* Header */}
        <div
          className={cn(
            "flex shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-5 py-4 sm:px-6",
            headerClassName
          )}
        >
          <div className="min-w-0">
            <p
              className={cn(
                "text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500",
                eyebrowClassName
              )}
            >
              {eyebrow}
            </p>
            <h2
              className={cn(
                "truncate pr-3 text-lg font-semibold tracking-tight text-slate-950",
                titleClassName
              )}
            >
              {title}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-400 transition hover:bg-slate-50 hover:text-slate-700",
              closeButtonClassName
            )}
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </div>

        {/* Body */}
        <div
          className={cn(
            "min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6",
            bodyClassName
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}
