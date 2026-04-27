import { useEffect, useMemo, useState } from "react";

import { fetchLocationSuggestions } from "../../api/locations";
import type { LocationSuggestion } from "../../types/location";

interface LocationAutocompleteInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> {
  value: string;
  onChange: (value: string) => void;
}

export function LocationAutocompleteInput({
  value,
  onChange,
  className = "",
  ...props
}: LocationAutocompleteInputProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [highlightedIndex, setHighlightedIndex] = useState(0);

  const trimmedValue = value.trim();
  const showSuggestions = open && trimmedValue.length > 0 && suggestions.length > 0;

  useEffect(() => {
    if (!open || trimmedValue.length === 0) {
      setSuggestions([]);
      setHighlightedIndex(0);
      return;
    }

    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const next = await fetchLocationSuggestions(trimmedValue);
        setSuggestions(next);
        setHighlightedIndex(0);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 150);

    return () => window.clearTimeout(timer);
  }, [open, trimmedValue]);

  const helperText = useMemo(() => {
    if (loading) return "Searching locations...";
    if (trimmedValue.length > 0 && suggestions.length > 0) {
      return "Use arrow keys and Enter to pick a suggestion.";
    }
    return null;
  }, [loading, trimmedValue.length, suggestions.length]);

  function applySuggestion(suggestion: LocationSuggestion) {
    onChange(suggestion.label);
    setOpen(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!showSuggestions) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.min(current + 1, suggestions.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
      return;
    }

    if (event.key === "Enter" && suggestions[highlightedIndex]) {
      event.preventDefault();
      applySuggestion(suggestions[highlightedIndex]);
      return;
    }

    if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <input
        {...props}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onKeyDown={handleKeyDown}
        className={`h-10 w-full rounded-[10px] border-[1.5px] border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500 ${className}`}
      />

      {showSuggestions ? (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-[12px] border border-slate-200 bg-white p-1 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.kind}-${suggestion.label}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => applySuggestion(suggestion)}
              className={`flex w-full items-start justify-between gap-3 rounded-[10px] px-3 py-2 text-left transition ${
                index === highlightedIndex ? "bg-indigo-50" : "hover:bg-slate-50"
              }`}
            >
              <div>
                <div className="text-sm font-medium text-slate-900">{suggestion.label}</div>
                <div className="mt-0.5 text-xs text-slate-400">
                  {suggestion.kind === "airport_code" ? "Airport code" : "Resolved codes"}
                </div>
              </div>
              <div className="text-xs font-medium text-slate-500">
                {suggestion.codes.slice(0, 3).join(", ")}
                {suggestion.codes.length > 3 ? ` +${suggestion.codes.length - 3}` : ""}
              </div>
            </button>
          ))}
        </div>
      ) : null}

      {helperText ? <p className="mt-1.5 text-xs text-slate-400">{helperText}</p> : null}
    </div>
  );
}
