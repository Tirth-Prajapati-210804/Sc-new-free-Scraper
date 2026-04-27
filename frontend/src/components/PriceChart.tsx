import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceTrend } from "../types/price";

interface PriceChartProps {
  data: PriceTrend[];
}

function fmtDate(d: unknown): string {
  if (typeof d !== "string") return String(d ?? "");
  return new Date(d + "T00:00:00").toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
  });
}

interface CustomTooltipProps {
  active?: boolean;
  label?: string;
  payload?: Array<{ payload: PriceTrend }>;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload as PriceTrend;
  return (
    <div
      className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-md"
      style={{ fontSize: 13 }}
    >
      <p className="mb-1 font-medium text-slate-700">{fmtDate(label)}</p>
      <p className="text-brand-600 font-semibold">
        ${Number(point.price).toLocaleString()}
      </p>
      {point.airline && (
        <p className="mt-0.5 text-xs text-slate-400">{point.airline}</p>
      )}
    </div>
  );
}

export function PriceChart({ data }: PriceChartProps) {
  if (!data.length) {
    return (
      <p className="py-12 text-center text-sm text-slate-400">
        No price data available
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.22} />
            <stop offset="95%" stopColor="#4f46e5" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12, fill: "#64748b" }}
          tickFormatter={fmtDate}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "#64748b" }}
          tickFormatter={(v: unknown) => `$${Number(v).toLocaleString()}`}
          width={68}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="price"
          stroke="#4f46e5"
          strokeWidth={2}
          fill="url(#priceGradient)"
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
