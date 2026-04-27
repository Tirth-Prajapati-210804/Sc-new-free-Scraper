/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useState,
} from "react";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { cn } from "../utils/cn";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let counter = 0;

const toastStyle: Record<ToastType, { border: string; icon: string; bg: string }> = {
  success: { border: "border-l-green-500", icon: "text-green-500", bg: "" },
  error:   { border: "border-l-red-500",   icon: "text-red-500",   bg: "" },
  info:    { border: "border-l-brand-500", icon: "text-brand-500", bg: "" },
};

const ToastIcon: Record<ToastType, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++counter;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast stack — top-right */}
      <div className="fixed right-4 top-4 z-[100] flex flex-col gap-2">
        {toasts.map((toast) => {
          const style = toastStyle[toast.type];
          const Icon = ToastIcon[toast.type];
          return (
            <div
              key={toast.id}
              className={cn(
                "toast-animate flex items-start gap-3 rounded-lg border border-slate-200 border-l-4 bg-white px-4 py-3 shadow-lg",
                "min-w-[280px] max-w-sm",
                style.border,
              )}
            >
              <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", style.icon)} aria-hidden="true" />
              <p className="flex-1 text-sm font-medium text-slate-700">{toast.message}</p>
              <button
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                className="flex-shrink-0 text-slate-300 hover:text-slate-500"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
