import { type ComponentPropsWithoutRef, type ReactNode } from "react";
import { cn } from "../../utils/cn";

interface CardProps extends ComponentPropsWithoutRef<"div"> {
  children: ReactNode;
}

export function Card({
  children,
  className,
  ...props
}: CardProps) {
  return (
    <div
      {...props}
      className={cn(
        "max-w-full min-w-0 rounded-[28px] border border-slate-200/90 bg-white p-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)] transition-all duration-200",
        className
      )}
    >
      {children}
    </div>
  );
}
