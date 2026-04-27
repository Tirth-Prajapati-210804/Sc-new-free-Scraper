interface DateRangeInputProps {
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
}

export function DateRangeInput({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: DateRangeInputProps) {
  return (
    <div className="flex items-center gap-2">
      <div>
        <label className="field-label">From</label>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFromChange(e.target.value)}
          className="field-input"
        />
      </div>
      <div className="mt-5 text-slate-400">–</div>
      <div>
        <label className="field-label">To</label>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => onDateToChange(e.target.value)}
          className="field-input"
        />
      </div>
    </div>
  );
}
