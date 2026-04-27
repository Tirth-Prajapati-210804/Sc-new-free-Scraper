import { useEffect } from "react";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} — Flight Price Tracker` : "Flight Price Tracker";
    return () => {
      document.title = "Flight Price Tracker";
    };
  }, [title]);
}
