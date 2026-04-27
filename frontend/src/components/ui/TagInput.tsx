import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { fetchLocationSuggestions } from "../../api/locations";
import type { LocationSuggestion } from "../../types/location";

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  hint?: string;
  className?: string;
  hintClassName?: string;
  inputClassName?: string;
}

const IATA_RE = /^[A-Za-z0-9]{2,4}$/;

export function TagInput({
  value,
  onChange,
  placeholder = "e.g. YYZ",
  hint,
  className,
  hintClassName,
  inputClassName,
}: TagInputProps) {
  const [input, setInput] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<LocationSuggestion[]>([]);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const trimmedInput = input.trim();
  const showSuggestions = open && trimmedInput.length > 0 && suggestions.length > 0;

  useEffect(() => {
    if (!open || trimmedInput.length === 0) {
      setSuggestions([]);
      setHighlightedIndex(0);
      return;
    }

    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const next = await fetchLocationSuggestions(trimmedInput);
        setSuggestions(next);
        setHighlightedIndex(0);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    }, 150);

    return () => window.clearTimeout(timer);
  }, [open, trimmedInput]);

  function tryAdd(raw: string) {
    const code = raw.trim().toUpperCase();

    if (!code) {
      return;
    }

    if (!IATA_RE.test(code)) {
      setInvalid(true);
      return;
    }

    setInvalid(false);

    if (!value.includes(code)) {
      onChange([...value, code]);
    }

    setInput("");
  }

  function addSuggestion(suggestion: LocationSuggestion) {
    const merged = [...value];
    suggestion.codes.forEach((code) => {
      const normalized = code.trim().toUpperCase();
      if (normalized && !merged.includes(normalized)) {
        merged.push(normalized);
      }
    });
    onChange(merged);
    setInput("");
    setInvalid(false);
    setOpen(false);
  }

  function remove(tag: string) {
    onChange(value.filter((item) => item !== tag));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (showSuggestions && e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((current) => Math.min(current + 1, suggestions.length - 1));
      return;
    }

    if (showSuggestions && e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
      return;
    }

    if (e.key === "Enter" || e.key === "," || e.key === "Tab") {
      e.preventDefault();
      if (showSuggestions && suggestions[highlightedIndex]) {
        addSuggestion(suggestions[highlightedIndex]);
        return;
      }
      tryAdd(input);
      return;
    }

    if (e.key === "Backspace" && input === "" && value.length > 0) {
      onChange(value.slice(0, -1));
      return;
    }

    if (e.key === "Escape") {
      setOpen(false);
    }

    setInvalid(false);
  }

  function handleBlur() {
    window.setTimeout(() => setOpen(false), 120);
    if (input.trim() && !showSuggestions) {
      tryAdd(input);
    }
  }

  return (
    <div className="space-y-1.5">
      <div
        ref={containerRef}
        onClick={() => containerRef.current?.querySelector("input")?.focus()}
        className={`tag-input-wrap min-h-[46px] w-full cursor-text rounded-[10px] border bg-white px-3 py-2 transition ${
          invalid
            ? "border-red-400 ring-4 ring-red-100"
            : "border-slate-200 hover:border-slate-300 focus-within:border-brand-500"
        } ${className ?? ""}`}
      >
        <div className="flex flex-wrap items-center gap-1.5">
          {value.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-brand-700"
            >
              {tag}
              <button
                type="button"
                aria-label={`Remove ${tag}`}
                onClick={(e) => {
                  e.stopPropagation();
                  remove(tag);
                }}
                className="rounded-full p-0.5 text-brand-500 transition hover:bg-white hover:text-brand-800"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}

          <input
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              setInvalid(false);
              setOpen(true);
            }}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onFocus={() => setOpen(true)}
            placeholder={value.length === 0 ? placeholder : ""}
            className={`h-7 min-w-[90px] flex-1 border-none bg-transparent p-0 text-sm text-slate-900 outline-none placeholder:text-slate-400 ${inputClassName ?? ""}`}
          />
        </div>
      </div>

      {showSuggestions ? (
        <div className="rounded-[12px] border border-slate-200 bg-white p-1 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.kind}-${suggestion.label}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => addSuggestion(suggestion)}
              className={`flex w-full items-start justify-between gap-3 rounded-[10px] px-3 py-2 text-left transition ${
                index === highlightedIndex ? "bg-indigo-50" : "hover:bg-slate-50"
              }`}
            >
              <div>
                <div className="text-sm font-medium text-slate-900">{suggestion.label}</div>
                <div className="mt-0.5 text-xs text-slate-400">
                  {suggestion.kind === "airport_code" ? "Add code" : "Add resolved airport codes"}
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

      {invalid ? (
        <p className="text-xs text-red-500">
          Use a valid IATA code with 2 to 4 letters or digits, or choose a suggestion.
        </p>
      ) : (
        <p className={`text-[11px] text-slate-400 ${hintClassName ?? ""}`}>
          {loading
            ? "Searching locations..."
            : hint ?? "Press Enter, comma, or Tab to add airports, or choose a suggestion."}
        </p>
      )}
    </div>
  );
}
