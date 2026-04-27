import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  Plane,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "./ui/Button";
import { LocationAutocompleteInput } from "./ui/LocationAutocompleteInput";
import { Modal } from "./ui/Modal";
import { TagInput } from "./ui/TagInput";

import {
  createRouteGroup,
  createRouteGroupFromText,
  updateRouteGroup,
} from "../api/route-groups";
import { getErrorMessage } from "../api/client";
import { useToast } from "../context/ToastContext";
import type { RouteGroup, SpecialSheet, TripType } from "../types/route-group";

interface RouteGroupFormProps {
  open: boolean;
  onClose: () => void;
  initial?: RouteGroup | null;
}

type UiTripType = "roundtrip" | "oneway" | "multicity";

interface ManualLeg {
  from: string[];
  to: string[];
  name: string;
  city: string;
}

interface QuickExtraLeg {
  from: string;
  to: string;
}

interface QuickState {
  from: string;
  to: string;
  nights: string;
  days: string;
  currency: string;
  startDate: string;
  endDate: string;
  stops: string;
  extraLegs: QuickExtraLeg[];
}

interface ManualState {
  tripType: UiTripType;
  mainLeg: ManualLeg;
  extraLegs: ManualLeg[];
  nights: string;
  days: string;
  currency: string;
  startDate: string;
  endDate: string;
  stops: string;
  isActive: boolean;
}

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "SGD", "AED", "INR"];

const TRIP_TYPES: Array<{
  id: UiTripType;
  label: string;
  description: string;
}> = [
  { id: "roundtrip", label: "Round Trip", description: "Outbound + return leg" },
  { id: "oneway", label: "One Way", description: "Single outbound leg" },
  { id: "multicity", label: "Multi-city", description: "Custom leg sequence" },
];

const STOP_OPTIONS = [
  { id: "any", label: "Any", value: null as number | null },
  { id: "direct", label: "Direct", value: 0 },
  { id: "prefer-1", label: "Prefer 1", value: 3 },
  { id: "1-stop", label: "1 Stop", value: 1 },
  { id: "2-stops", label: "2 Stops", value: 2 },
];

function emptyLeg(): ManualLeg {
  return { from: [], to: [], name: "", city: "" };
}

function tripTypeToUi(type?: TripType | null): UiTripType {
  if (type === "multi_city") return "multicity";
  if (type === "one_way") return "oneway";
  return "roundtrip";
}

function tripTypeToApi(type: UiTripType): TripType {
  if (type === "multicity") return "multi_city";
  if (type === "oneway") return "one_way";
  return "round_trip";
}

function stopToUi(value: number | null | undefined): string {
  return STOP_OPTIONS.find((option) => option.value === value)?.id ?? "any";
}

function stopToApi(value: string): number | null {
  return STOP_OPTIONS.find((option) => option.id === value)?.value ?? null;
}

function parsePositiveInt(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeCodes(values: string[]) {
  return values.map((item) => item.trim().toUpperCase()).filter(Boolean);
}

function deriveName(origins: string[], destinations: string[]) {
  return `${origins.join(", ")} to ${destinations.join(", ")}`;
}

function buildInitialManualState(initial?: RouteGroup | null): ManualState {
  const tripType = tripTypeToUi(initial?.trip_type);
  return {
    tripType,
    mainLeg: {
      from: initial?.origins ?? [],
      to: initial?.destinations ?? [],
      name: initial?.name ?? "",
      city: initial?.destination_label ?? "",
    },
    extraLegs:
      initial?.special_sheets.map((sheet) => ({
        from: [sheet.origin],
        to: sheet.destinations,
        name: sheet.name,
        city: sheet.destination_label,
      })) ?? [],
    nights: String(initial?.nights ?? 10),
    days: String(initial?.days_ahead ?? 365),
    currency: initial?.currency ?? "USD",
    startDate: initial?.start_date ?? "",
    endDate: initial?.end_date ?? "",
    stops: stopToUi(initial?.max_stops),
    isActive: initial?.is_active ?? true,
  };
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="mb-1.5 block text-xs font-medium text-slate-500">
      {children}
    </label>
  );
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="mt-1.5 text-xs text-slate-400">{children}</p>;
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-10 w-full rounded-[10px] border-[1.5px] border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500 ${props.className ?? ""}`}
    />
  );
}

function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        {...props}
        className={`h-10 w-full appearance-none rounded-[10px] border-[1.5px] border-slate-200 bg-white px-3 pr-8 text-sm text-slate-900 outline-none transition focus:border-brand-500 ${props.className ?? ""}`}
      />
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

function TripTypeSelector({
  tripType,
  onChange,
}: {
  tripType: UiTripType;
  onChange: (value: UiTripType) => void;
}) {
  return (
    <div className="mb-5">
      <div className="mb-2.5 text-xs font-semibold text-slate-600">Trip Type</div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {TRIP_TYPES.map((type) => {
          const active = tripType === type.id;
          return (
            <button
              key={type.id}
              type="button"
              onClick={() => onChange(type.id)}
              className={`rounded-[10px] border-[1.5px] px-3 py-3 text-left transition ${
                active
                  ? "border-brand-500 bg-indigo-50"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <div className={`text-sm font-semibold ${active ? "text-brand-700" : "text-slate-900"}`}>
                {type.label}
              </div>
              <div className="mt-1 text-xs text-slate-400">{type.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StopSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <div className="mb-2 text-xs font-medium text-slate-500">Connection Filter</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {STOP_OPTIONS.map((option) => {
          const active = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange(option.id)}
              className={`rounded-[8px] border-[1.5px] px-2 py-2 text-xs font-medium transition ${
                active
                  ? "border-brand-500 bg-indigo-50 text-brand-700"
                  : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AdvancedSettings({
  currency,
  setCurrency,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  stops,
  setStops,
}: {
  currency: string;
  setCurrency: (value: string) => void;
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  stops: string;
  setStops: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-[10px] border border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium text-slate-600"
      >
        <span>Advanced Settings</span>
        <ChevronDown className={`h-4 w-4 text-slate-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="space-y-4 border-t border-slate-200 px-4 pb-4 pt-2">
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <Label>Currency</Label>
              <SelectInput value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </SelectInput>
            </div>
            <div>
              <Label>Start Date</Label>
              <TextInput type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div>
              <Label>End Date</Label>
              <TextInput type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <StopSelector value={stops} onChange={setStops} />
        </div>
      ) : null}
    </div>
  );
}

function ManualLegCard({
  leg,
  label,
  removable,
  onRemove,
  onChange,
}: {
  leg: ManualLeg;
  label: string;
  removable: boolean;
  onRemove?: () => void;
  onChange: (next: ManualLeg) => void;
}) {
  function patch<K extends keyof ManualLeg>(key: K, value: ManualLeg[K]) {
    onChange({ ...leg, [key]: value });
  }

  return (
    <div className="overflow-hidden rounded-[10px] border-[1.5px] border-slate-200">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-50 text-brand-700">
            <Plane className="h-3.5 w-3.5" />
          </div>
          <span className="text-xs font-semibold text-brand-700">{label}</span>
        </div>
        {removable ? (
          <button
            type="button"
            onClick={onRemove}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-red-500 transition hover:bg-red-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove
          </button>
        ) : null}
      </div>

      <div className="space-y-3 p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-end">
          <div>
            <Label>Departure Airports</Label>
            <TagInput
              value={leg.from}
              onChange={(value) => patch("from", value)}
              placeholder="e.g. YYZ, YVR"
              hint="Separate codes with Enter or comma"
            />
          </div>
          <div className="flex items-center justify-center pb-6">
            <div className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400">
              <ChevronRight className="h-4 w-4" />
            </div>
          </div>
          <div>
            <Label>Arrival Airports</Label>
            <TagInput
              value={leg.to}
              onChange={(value) => patch("to", value)}
              placeholder="e.g. BER, MUC"
              hint="Separate codes with Enter or comma"
            />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Label>Route Name</Label>
            <TextInput
              value={leg.name}
              onChange={(e) => patch("name", e.target.value)}
              placeholder="e.g. Canada to Berlin"
            />
          </div>
          <div>
            <Label>Destination Label</Label>
            <TextInput
              value={leg.city}
              onChange={(e) => patch("city", e.target.value)}
              placeholder="e.g. Berlin"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickSetupForm({
  state,
  setState,
  tripType,
  onSubmit,
  saving,
  onClose,
  error,
}: {
  state: QuickState;
  setState: React.Dispatch<React.SetStateAction<QuickState>>;
  tripType: UiTripType;
  onSubmit: (e: FormEvent) => void;
  saving: boolean;
  onClose: () => void;
  error: string;
}) {
  function patch<K extends keyof QuickState>(key: K, value: QuickState[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function swapQuickRoute() {
    setState((current) => ({
      ...current,
      from: current.to,
      to: current.from,
    }));
  }

  function addExtraLeg() {
    setState((current) => ({
      ...current,
      extraLegs: [...current.extraLegs, { from: "", to: "" }],
    }));
  }

  function updateExtraLeg(index: number, next: QuickExtraLeg) {
    setState((current) => ({
      ...current,
      extraLegs: current.extraLegs.map((item, itemIndex) =>
        itemIndex === index ? next : item,
      ),
    }));
  }

  function removeExtraLeg(index: number) {
    setState((current) => ({
      ...current,
      extraLegs: current.extraLegs.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div>
        <div className="mb-2.5 text-xs font-semibold text-slate-600">
          {tripType === "oneway" ? "Flight" : "Outbound Leg"}
        </div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-end">
          <div>
            <Label>Departure</Label>
            <LocationAutocompleteInput
              value={state.from}
              onChange={(next) => patch("from", next)}
              placeholder="City name or airport code"
              required
            />
          </div>
          <div className="flex items-center justify-center pb-1">
            <button
              type="button"
              onClick={swapQuickRoute}
              className="flex h-8 w-8 items-center justify-center rounded-full border-[1.5px] border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50"
              aria-label="Swap departure and destination"
            >
              <ArrowLeftRight className="h-4 w-4" />
            </button>
          </div>
          <div>
            <Label>Destination</Label>
            <LocationAutocompleteInput
              value={state.to}
              onChange={(next) => patch("to", next)}
              placeholder="City name or airport code"
              required
            />
          </div>
        </div>
      </div>

      {tripType === "roundtrip" ? (
        <div className="rounded-[10px] border-[1.5px] border-slate-200 bg-slate-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-xs font-semibold text-slate-600">Return Leg</span>
            <span className="text-xs text-slate-400">Auto-generated from outbound</span>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="rounded-[8px] border-[1.5px] border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-400">
              {state.to || "Berlin / BER"}
            </div>
            <ChevronRight className="mx-auto h-4 w-4 text-slate-300" />
            <div className="rounded-[8px] border-[1.5px] border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-400">
              {state.from || "Toronto / YYZ"}
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Return date is offset from departure by your nights at destination.
          </div>
        </div>
      ) : null}

      {tripType === "multicity" ? (
        <div>
          <div className="mb-2.5 text-xs font-semibold text-slate-600">Additional Legs</div>
          <div className="space-y-3">
            {state.extraLegs.map((leg, index) => (
              <div key={index} className="rounded-[10px] border-[1.5px] border-slate-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-semibold text-brand-700">Leg {index + 2}</span>
                  <button
                    type="button"
                    onClick={() => removeExtraLeg(index)}
                    className="inline-flex items-center gap-1 text-xs text-red-500"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove
                  </button>
                </div>
                <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-end">
                  <div>
                    <Label>Departure</Label>
                    <LocationAutocompleteInput
                      value={leg.from}
                      onChange={(next) => updateExtraLeg(index, { ...leg, from: next })}
                      placeholder="e.g. Toronto"
                    />
                  </div>
                  <div className="flex items-center justify-center pb-1">
                    <ChevronRight className="h-4 w-4 text-slate-300" />
                  </div>
                  <div>
                    <Label>Destination</Label>
                    <LocationAutocompleteInput
                      value={leg.to}
                      onChange={(next) => updateExtraLeg(index, { ...leg, to: next })}
                      placeholder="e.g. Berlin"
                    />
                  </div>
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={addExtraLeg}
              className="flex w-full items-center justify-center gap-2 rounded-[8px] border-[1.5px] border-dashed border-indigo-200 bg-indigo-50 px-3 py-2.5 text-sm font-medium text-brand-700"
            >
              <Plus className="h-4 w-4" />
              Add Leg
            </button>
            <div className="text-xs text-slate-400">
              City names or airport codes are resolved automatically for each added leg.
            </div>
          </div>
        </div>
      ) : null}

      <div>
        <div className="mb-2.5 text-xs font-semibold text-slate-600">Tracking Window</div>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Label>Nights at Destination</Label>
            <TextInput
              value={state.nights}
              onChange={(e) => patch("nights", e.target.value)}
              type="number"
              min={1}
            />
          </div>
          <div>
            <Label>Booking Window (days)</Label>
            <TextInput
              value={state.days}
              onChange={(e) => patch("days", e.target.value)}
              type="number"
              min={1}
            />
            <FieldHint>How many days ahead to scan</FieldHint>
          </div>
        </div>
      </div>

      <AdvancedSettings
        currency={state.currency}
        setCurrency={(value) => patch("currency", value)}
        startDate={state.startDate}
        setStartDate={(value) => patch("startDate", value)}
        endDate={state.endDate}
        setEndDate={(value) => patch("endDate", value)}
        stops={state.stops}
        setStops={(value) => patch("stops", value)}
      />

      {error ? (
        <div className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="flex items-center justify-between border-t border-slate-200 pt-4">
        <div className="text-xs text-slate-400">
          {tripType === "multicity"
            ? "Quick setup will create every leg and resolve locations automatically."
            : "You can refine the route group after it is created."}
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Create Group
          </Button>
        </div>
      </div>
    </form>
  );
}

function CustomBuilderForm({
  state,
  setState,
  isEditing,
  onSubmit,
  saving,
  onClose,
  error,
}: {
  state: ManualState;
  setState: React.Dispatch<React.SetStateAction<ManualState>>;
  isEditing: boolean;
  onSubmit: (e: FormEvent) => void;
  saving: boolean;
  onClose: () => void;
  error: string;
}) {
  function patch<K extends keyof ManualState>(key: K, value: ManualState[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function updateMainLeg(next: ManualLeg) {
    patch("mainLeg", next);
  }

  function updateExtraLeg(index: number, next: ManualLeg) {
    patch(
      "extraLegs",
      state.extraLegs.map((item, itemIndex) => (itemIndex === index ? next : item)),
    );
  }

  function removeExtraLeg(index: number) {
    patch(
      "extraLegs",
      state.extraLegs.filter((_, itemIndex) => itemIndex !== index),
    );
  }

  function addExtraLeg() {
    patch("extraLegs", [...state.extraLegs, emptyLeg()]);
  }

  const returnFrom = state.mainLeg.to.join(", ") || "Berlin / BER";
  const returnTo = state.mainLeg.from.join(", ") || "Toronto / YYZ";

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div>
        <div className="mb-2.5 text-xs font-semibold text-slate-600">
          {state.tripType === "oneway" ? "Flight Leg" : "Outbound Leg"}
        </div>
        <ManualLegCard
          leg={state.mainLeg}
          label={state.tripType === "oneway" ? "Flight" : "Outbound"}
          removable={false}
          onChange={updateMainLeg}
        />
      </div>

      {state.tripType === "roundtrip" ? (
        <div className="rounded-[10px] border-[1.5px] border-slate-200 bg-slate-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-xs font-semibold text-slate-600">Return Leg</span>
            <span className="text-xs text-slate-400">Auto-generated from outbound</span>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="rounded-[8px] border-[1.5px] border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-500">
              {returnFrom}
            </div>
            <ChevronRight className="mx-auto h-4 w-4 text-slate-300" />
            <div className="rounded-[8px] border-[1.5px] border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-500">
              {returnTo}
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Return date is offset from departure by your nights at destination.
          </div>
        </div>
      ) : null}

      {state.tripType === "multicity" ? (
        <div>
          <div className="mb-2.5 text-xs font-semibold text-slate-600">Additional Legs</div>
          <div className="space-y-3">
            {state.extraLegs.map((leg, index) => (
              <ManualLegCard
                key={index}
                leg={leg}
                label={`Leg ${index + 2}`}
                removable={true}
                onRemove={() => removeExtraLeg(index)}
                onChange={(next) => updateExtraLeg(index, next)}
              />
            ))}
            <button
              type="button"
              onClick={addExtraLeg}
              className="flex w-full items-center justify-center gap-2 rounded-[8px] border-[1.5px] border-dashed border-indigo-200 bg-indigo-50 px-3 py-2.5 text-sm font-medium text-brand-700"
            >
              <Plus className="h-4 w-4" />
              Add Leg
            </button>
          </div>
        </div>
      ) : null}

      <div>
        <div className="mb-2.5 text-xs font-semibold text-slate-600">Tracking Window</div>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <Label>Nights at Destination</Label>
            <TextInput
              value={state.nights}
              onChange={(e) => patch("nights", e.target.value)}
              type="number"
              min={1}
            />
          </div>
          <div>
            <Label>Booking Window (days)</Label>
            <TextInput
              value={state.days}
              onChange={(e) => patch("days", e.target.value)}
              type="number"
              min={1}
            />
          </div>
        </div>
      </div>

      <AdvancedSettings
        currency={state.currency}
        setCurrency={(value) => patch("currency", value)}
        startDate={state.startDate}
        setStartDate={(value) => patch("startDate", value)}
        endDate={state.endDate}
        setEndDate={(value) => patch("endDate", value)}
        stops={state.stops}
        setStops={(value) => patch("stops", value)}
      />

      {isEditing ? (
        <label className="flex items-center gap-2 rounded-[10px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={state.isActive}
            onChange={(e) => patch("isActive", e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Keep this route group active
        </label>
      ) : null}

      {error ? (
        <div className="rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      <div className="flex items-center justify-between border-t border-slate-200 pt-4">
        <div className="text-xs text-slate-400">
          {state.tripType === "multicity"
            ? "Extra legs become special sheets in the backend."
            : "Airport tags accept Enter, comma, or Tab."}
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            {isEditing ? "Save Changes" : "Create Group"}
          </Button>
        </div>
      </div>
    </form>
  );
}

export function RouteGroupForm({
  open,
  onClose,
  initial,
}: RouteGroupFormProps) {
  const qc = useQueryClient();
  const { showToast } = useToast();
  const [tab, setTab] = useState<"quick" | "manual">(initial ? "manual" : "quick");
  const [tripType, setTripType] = useState<UiTripType>(tripTypeToUi(initial?.trip_type));
  const [quickState, setQuickState] = useState<QuickState>({
    from: "",
    to: "",
    nights: "10",
    days: "365",
    currency: "USD",
    startDate: "",
    endDate: "",
    stops: "any",
    extraLegs: [],
  });
  const [manualState, setManualState] = useState<ManualState>(() => buildInitialManualState(initial));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;

    setTab(initial ? "manual" : "quick");
    setTripType(tripTypeToUi(initial?.trip_type));
    setError("");
    setQuickState({
      from: "",
      to: "",
      nights: "10",
      days: "365",
      currency: "USD",
      startDate: "",
      endDate: "",
      stops: "any",
      extraLegs: [],
    });
    setManualState(buildInitialManualState(initial));
  }, [initial, open]);

  useEffect(() => {
    setManualState((current) => ({ ...current, tripType }));
  }, [tripType]);

  const modalTitle = initial ? "Edit Route Group" : "New Route Group";
  const isEditing = Boolean(initial);

  const summary = useMemo(() => {
    const routeCount = manualState.tripType === "multicity" ? manualState.extraLegs.length + 1 : 1;
    return {
      routeCount,
      originCount: manualState.mainLeg.from.length,
      destinationCount: manualState.mainLeg.to.length,
      name: manualState.mainLeg.name || deriveName(manualState.mainLeg.from, manualState.mainLeg.to) || "Untitled route group",
    };
  }, [manualState]);

  async function refreshQueries(groupId?: string) {
    await qc.invalidateQueries({ queryKey: ["route-groups"] });
    if (groupId) {
      await qc.invalidateQueries({ queryKey: ["route-group", groupId] });
    }
  }

  async function handleQuickSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const created = await createRouteGroupFromText({
        origin: quickState.from.trim(),
        destination: quickState.to.trim(),
        nights: parsePositiveInt(quickState.nights, 10),
        days_ahead: parsePositiveInt(quickState.days, 365),
        currency: quickState.currency,
        max_stops: stopToApi(quickState.stops),
        start_date: quickState.startDate || null,
        end_date: quickState.endDate || null,
        trip_type: tripTypeToApi(tripType),
        extra_legs:
          tripType === "multicity"
            ? quickState.extraLegs.map((leg) => ({
                origin: leg.from.trim(),
                destination: leg.to.trim(),
              }))
            : [],
      });

      await refreshQueries(created.group.id);
      showToast(`Created: ${created.group.name}`, "success");
      onClose();
    } catch (err) {
      setError(getErrorMessage(err, "Could not create route group."));
    } finally {
      setSaving(false);
    }
  }

  async function handleManualSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      const mainOrigins = normalizeCodes(manualState.mainLeg.from);
      const mainDestinations = normalizeCodes(manualState.mainLeg.to);

      if (!mainOrigins.length || !mainDestinations.length) {
        throw new Error("Add at least one origin and one destination in the main leg.");
      }

      const specialSheets: SpecialSheet[] = [];

      if (manualState.tripType === "multicity") {
        manualState.extraLegs.forEach((leg, index) => {
          const origins = normalizeCodes(leg.from);
          const destinations = normalizeCodes(leg.to);

          if (!origins.length || !destinations.length) {
            throw new Error(`Complete all airports for leg ${index + 2}.`);
          }

          origins.forEach((origin, originIndex) => {
            specialSheets.push({
              name: leg.name.trim() || `Leg ${index + 2}${origins.length > 1 ? ` ${originIndex + 1}` : ""}`,
              origin,
              destination_label: leg.city.trim() || destinations.join("/"),
              destinations,
              columns: 4,
            });
          });
        });
      }

      const payload = {
        name: manualState.mainLeg.name.trim() || deriveName(mainOrigins, mainDestinations),
        destination_label: manualState.mainLeg.city.trim() || mainDestinations.join("/"),
        origins: mainOrigins,
        destinations: mainDestinations,
        nights: parsePositiveInt(manualState.nights, 10),
        days_ahead: parsePositiveInt(manualState.days, 365),
        sheet_name_map: Object.fromEntries(mainOrigins.map((origin) => [origin, origin])),
        special_sheets: specialSheets,
        currency: manualState.currency,
        max_stops: stopToApi(manualState.stops),
        start_date: manualState.startDate || null,
        end_date: manualState.endDate || null,
        trip_type: tripTypeToApi(manualState.tripType),
        ...(isEditing ? { is_active: manualState.isActive } : {}),
      };

      if (initial) {
        await updateRouteGroup(initial.id, payload);
        await refreshQueries(initial.id);
        showToast("Route group saved", "success");
      } else {
        const created = await createRouteGroup(payload);
        await refreshQueries(created.id);
        showToast(`Created: ${created.name}`, "success");
      }

      onClose();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save route group."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={modalTitle}
      size="lg"
      className="max-w-[720px] bg-white"
    >
      {!isEditing ? (
        <div className="mb-4 rounded-[10px] bg-slate-100 p-1">
          <div className="grid grid-cols-2 gap-1">
            {[
              { id: "quick", label: "Quick Setup" },
              { id: "manual", label: "Custom Builder" },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id as "quick" | "manual")}
                className={`rounded-[8px] px-3 py-2 text-sm font-medium transition ${
                  tab === item.id
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-400"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <TripTypeSelector tripType={tripType} onChange={setTripType} />

      {tab === "quick" && !isEditing ? (
        <QuickSetupForm
          state={quickState}
          setState={setQuickState}
          tripType={tripType}
          onSubmit={handleQuickSubmit}
          saving={saving}
          onClose={onClose}
          error={error}
        />
      ) : (
        <>
          <CustomBuilderForm
            state={manualState}
            setState={setManualState}
            isEditing={isEditing}
            onSubmit={handleManualSubmit}
            saving={saving}
            onClose={onClose}
            error={error}
          />

          {!isEditing ? (
            <div className="mt-5 rounded-[12px] border border-slate-200 bg-slate-50 p-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Summary
              </div>
              <div className="text-sm font-semibold text-slate-900">{summary.name}</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <div className="rounded-[10px] border border-slate-200 bg-white px-3 py-2">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Origins</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{summary.originCount || "None yet"}</div>
                </div>
                <div className="rounded-[10px] border border-slate-200 bg-white px-3 py-2">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Destinations</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{summary.destinationCount || "None yet"}</div>
                </div>
                <div className="rounded-[10px] border border-slate-200 bg-white px-3 py-2">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Journeys</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{summary.routeCount}</div>
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </Modal>
  );
}
