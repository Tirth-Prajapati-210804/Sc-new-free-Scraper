import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  ChevronDown,
  ChevronRight,
  Plane,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";
import { TagInput } from "./ui/TagInput";

import {
  createRouteGroup,
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
  { id: "prefer-1", label: "Prefer 1 Stop", value: 3 },
  { id: "direct", label: "Direct Only", value: 0 },
  { id: "1-stop", label: "Up to 1 Stop", value: 1 },
  { id: "2-stops", label: "Up to 2 Stops", value: 2 },
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
  return STOP_OPTIONS.find((option) => option.value === value)?.id ?? "prefer-1";
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
    <label className="mb-2 block text-[12px] font-medium text-slate-500">
      {children}
    </label>
  );
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-[11px] text-slate-400">{children}</p>;
}

function SectionHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-2.5">
      <div className="text-[12px] font-semibold text-slate-600">{title}</div>
      {subtitle ? <div className="mt-1 text-[11px] text-slate-400">{subtitle}</div> : null}
    </div>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-[46px] w-full rounded-[10px] border border-slate-200 bg-white px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500 ${props.className ?? ""}`}
    />
  );
}

function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className="relative">
      <select
        {...props}
        className={`h-[46px] w-full appearance-none rounded-[10px] border border-slate-200 bg-white px-4 pr-9 text-sm text-slate-900 outline-none transition focus:border-brand-500 ${props.className ?? ""}`}
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
    <div className="mb-6">
      <div className="mb-2.5 text-[12px] font-semibold text-slate-600">Trip Type</div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {TRIP_TYPES.map((type) => {
          const active = tripType === type.id;
          return (
            <button
              key={type.id}
              type="button"
              onClick={() => onChange(type.id)}
              className={`rounded-[10px] border px-4 py-4 text-left transition ${
                active
                  ? "border-brand-500 bg-indigo-50"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <div className={`text-[15px] font-semibold ${active ? "text-brand-700" : "text-slate-900"}`}>
                {type.label}
              </div>
              <div className="mt-1 text-[12px] text-slate-400">{type.description}</div>
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
  tripType,
}: {
  value: string;
  onChange: (value: string) => void;
  tripType?: UiTripType;
}) {
  return (
    <div>
      <div className="mb-2 text-[12px] font-medium text-slate-500">Connection Filter</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {STOP_OPTIONS.map((option) => {
          const active = value === option.id;
          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange(option.id)}
              className={`rounded-[8px] border px-2 py-2.5 text-[12px] font-medium transition ${
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
      <FieldHint>
        {value === "prefer-1"
          ? "Recommended. Searches 1-stop first, then 2-stop, then direct if needed."
          : value === "1-stop"
            ? "Allows direct and 1-stop itineraries."
            : value === "2-stops"
              ? "Allows direct, 1-stop, and 2-stop itineraries."
              : value === "direct"
                ? "Only nonstop flights will be considered."
                : tripType === "multicity"
                  ? "Use Prefer 1 Stop for the client-style fallback behavior."
                  : "Choose how broadly the search can expand across stop counts."}
      </FieldHint>
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
  tripType,
}: {
  currency: string;
  setCurrency: (value: string) => void;
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  stops: string;
  setStops: (value: string) => void;
  tripType?: UiTripType;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-[10px] border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between px-4 py-[11px] text-left text-sm font-medium text-slate-600"
      >
        <span>Advanced Settings</span>
        <ChevronDown
          className={`h-4 w-4 text-slate-400 transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open ? (
        <div className="space-y-4 border-t border-slate-200 px-4 pb-4 pt-3">
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
          <StopSelector value={stops} onChange={setStops} tripType={tripType} />
        </div>
      ) : null}
    </div>
  );
}

function ManualLegCard({
  leg,
  label,
  removable,
  swapEnabled,
  onSwap,
  onRemove,
  onChange,
}: {
  leg: ManualLeg;
  label: string;
  removable: boolean;
  swapEnabled?: boolean;
  onSwap?: () => void;
  onRemove?: () => void;
  onChange: (next: ManualLeg) => void;
}) {
  function patch<K extends keyof ManualLeg>(key: K, value: ManualLeg[K]) {
    onChange({ ...leg, [key]: value });
  }

  return (
    <div className="overflow-hidden rounded-[10px] border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/70 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-6 w-6 items-center justify-center rounded-full border border-indigo-100 bg-white text-brand-700">
            <Plane className="h-3.5 w-3.5" />
          </div>
          <span className="text-sm font-semibold text-slate-800">{label}</span>
        </div>
        {removable ? (
          <button
            type="button"
            onClick={onRemove}
            className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium text-red-500 transition hover:bg-red-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Remove
          </button>
        ) : null}
      </div>

      <div className="space-y-3.5 p-4">
        <div className="grid gap-4 md:grid-cols-[1fr_42px_1fr] md:items-start">
          <div>
            <Label>Departure Airports</Label>
            <TagInput
              value={leg.from}
              onChange={(value) => patch("from", value)}
              placeholder="e.g. YYZ, YVR"
              hint="Press Enter, comma, or choose a suggestion."
            />
          </div>
          <div className="flex items-start justify-center pt-[30px]">
            {swapEnabled ? (
              <button
                type="button"
                onClick={onSwap}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:bg-slate-50"
                aria-label="Swap departure and arrival airports"
              >
                <ArrowLeftRight className="h-4 w-4" />
              </button>
            ) : (
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-400">
                <ChevronRight className="h-4 w-4" />
              </div>
            )}
          </div>
          <div>
            <Label>Arrival Airports</Label>
            <TagInput
              value={leg.to}
              onChange={(value) => patch("to", value)}
              placeholder="e.g. BER, MUC"
              hint="Press Enter, comma, or choose a suggestion."
            />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-3">
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            Optional Labels
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Route Name</Label>
              <TextInput
                value={leg.name}
                onChange={(e) => patch("name", e.target.value)}
                placeholder="Optional, e.g. Canada to Berlin"
              />
            </div>
            <div>
              <Label>Destination Label</Label>
              <TextInput
                value={leg.city}
                onChange={(e) => patch("city", e.target.value)}
                placeholder="Optional, e.g. Berlin"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
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

  function swapMainLeg() {
    updateMainLeg({
      ...state.mainLeg,
      from: state.mainLeg.to,
      to: state.mainLeg.from,
    });
  }

  const returnFrom = state.mainLeg.to.join(", ") || "Berlin / BER";
  const returnTo = state.mainLeg.from.join(", ") || "Toronto / YYZ";
  const returnLeg = state.extraLegs[0] ?? emptyLeg();

  return (
    <form onSubmit={onSubmit} className="space-y-6">
      <div>
        <SectionHeading
          title={state.tripType === "oneway" ? "Flight Leg" : "Outbound Leg"}
          subtitle="Use airport codes directly for exact route control."
        />
        <ManualLegCard
          leg={state.mainLeg}
          label={state.tripType === "oneway" ? "Flight" : "Outbound"}
          removable={false}
          swapEnabled={true}
          onSwap={swapMainLeg}
          onChange={updateMainLeg}
        />
      </div>

      {state.tripType === "roundtrip" ? (
        <div className="rounded-[10px] border border-slate-200 bg-slate-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-[12px] font-semibold text-slate-600">Return Leg</span>
            <span className="text-[12px] text-slate-400">Auto-generated from outbound</span>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <div className="rounded-[10px] border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-500">
              {returnFrom}
            </div>
            <ChevronRight className="mx-auto h-4 w-4 text-slate-300" />
            <div className="rounded-[10px] border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-500">
              {returnTo}
            </div>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            Return date is offset from departure by your nights at destination.
          </div>
        </div>
      ) : null}

      {state.tripType === "multicity" ? (
        <div>
          <SectionHeading
            title="Return Leg"
            subtitle="This mode searches one open-jaw itinerary total, not separate leg prices."
          />
          <div className="space-y-3 rounded-[10px] border border-slate-200 bg-white p-4">
            <div className="grid gap-4 md:grid-cols-[1fr_42px_1fr] md:items-start">
              <div>
                <Label>Return From Airports</Label>
                <TagInput
                  value={returnLeg.from}
                  onChange={(value) =>
                    patch("extraLegs", [{ ...returnLeg, from: value, to: state.mainLeg.from }])
                  }
                  placeholder="e.g. BUD"
                  hint="Use the airport or city you return from after the stay."
                />
              </div>
              <div className="flex items-start justify-center pt-[30px]">
                <div className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-400">
                  <ChevronRight className="h-4 w-4" />
                </div>
              </div>
              <div>
                <Label>Return To Airports</Label>
                <div className="flex min-h-[46px] items-center rounded-[10px] border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  {state.mainLeg.from.length ? state.mainLeg.from.join(", ") : "Original outbound origins"}
                </div>
                <FieldHint>Auto-linked back to your outbound origin.</FieldHint>
              </div>
            </div>
            <div className="rounded-[10px] bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
              For each departure date, the return date shifts by your stay nights and pricing comes back as one total itinerary fare.
            </div>
          </div>
        </div>
      ) : null}

      <div>
        <div className="mb-2.5 text-[12px] font-semibold text-slate-600">Tracking Window</div>
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
        tripType={state.tripType}
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

      <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-[11px] text-slate-400">
          {state.tripType === "multicity"
            ? "Export shows one itinerary total per date with the stop fallback result."
            : "Airport tags accept Enter, comma, or Tab."}
        </div>
        <div className="flex gap-2 self-end">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            className="rounded-[10px] shadow-none hover:translate-y-0 hover:shadow-none"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            loading={saving}
            className="rounded-[10px] shadow-none hover:translate-y-0 hover:shadow-none"
          >
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
  const [tripType, setTripType] = useState<UiTripType>(tripTypeToUi(initial?.trip_type));
  const [manualState, setManualState] = useState<ManualState>(() => buildInitialManualState(initial));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;

    setTripType(tripTypeToUi(initial?.trip_type));
    setError("");
    setManualState(buildInitialManualState(initial));
  }, [initial, open]);

  useEffect(() => {
    setManualState((current) => ({ ...current, tripType }));
  }, [tripType]);

  useEffect(() => {
    if (tripType !== "multicity") return;

    setManualState((current) => {
      const nextExtraLegs = current.extraLegs.length
        ? [{ ...current.extraLegs[0], to: current.mainLeg.from }]
        : [{ ...emptyLeg(), to: current.mainLeg.from }];

      return {
        ...current,
        stops: current.stops === "any" ? "prefer-1" : current.stops,
        extraLegs: nextExtraLegs,
      };
    });
  }, [tripType]);

  const modalTitle = initial ? "Edit Route Group" : "New Route Group";
  const isEditing = Boolean(initial);

  async function refreshQueries(groupId?: string) {
    await qc.invalidateQueries({ queryKey: ["route-groups"] });
    if (groupId) {
      await qc.invalidateQueries({ queryKey: ["route-group", groupId] });
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
        const returnOrigins = normalizeCodes(manualState.extraLegs[0]?.from ?? []);
        if (!returnOrigins.length) {
          throw new Error("Add at least one return-from airport for the open-jaw itinerary.");
        }

        specialSheets.push({
          name: "Return Leg",
          origin: returnOrigins[0],
          destination_label: manualState.mainLeg.city.trim() || mainOrigins.join("/"),
          destinations: mainOrigins,
          columns: 4,
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
      className="max-w-[900px] rounded-[28px] border-slate-200 bg-white shadow-[0_30px_90px_-48px_rgba(15,23,42,0.28)]"
      headerClassName="px-6 pb-4 pt-5 sm:px-6"
      bodyClassName="px-6 py-5 sm:px-6 sm:py-5"
      titleClassName="text-[18px] font-semibold tracking-tight text-slate-950"
      eyebrowClassName="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500"
      closeButtonClassName="h-[50px] w-[50px] rounded-[18px] border-slate-200 text-slate-300 hover:bg-slate-50 hover:text-slate-500"
    >
      <TripTypeSelector tripType={tripType} onChange={setTripType} />

      <CustomBuilderForm
        state={manualState}
        setState={setManualState}
        isEditing={isEditing}
        onSubmit={handleManualSubmit}
        saving={saving}
        onClose={onClose}
        error={error}
      />
    </Modal>
  );
}
