import { describe, it, expect } from "vitest";
import { formatNumber, formatRelativeTime, formatPercent } from "./format";

describe("formatNumber", () => {
  it("formats zero", () => {
    expect(formatNumber(0)).toBe("0");
  });

  it("formats small numbers without separators", () => {
    expect(formatNumber(999)).toBe("999");
  });

  it("formats large numbers with locale separators", () => {
    const result = formatNumber(1_000_000);
    expect(result).toContain("1");
    expect(result).toContain("000");
  });
});

describe("formatRelativeTime", () => {
  it("returns 'Never' for null", () => {
    expect(formatRelativeTime(null)).toBe("Never");
  });

  it("returns 'Never' for undefined", () => {
    expect(formatRelativeTime(undefined)).toBe("Never");
  });

  it("returns 'Just now' for 10 seconds ago", () => {
    const d = new Date(Date.now() - 10_000).toISOString();
    expect(formatRelativeTime(d)).toBe("Just now");
  });

  it("returns minutes ago for 5 minutes ago", () => {
    const d = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(formatRelativeTime(d)).toBe("5 min ago");
  });

  it("uses singular for 1 hour ago", () => {
    const d = new Date(Date.now() - 60 * 60_000).toISOString();
    expect(formatRelativeTime(d)).toBe("1 hour ago");
  });

  it("uses plural for 3 hours ago", () => {
    const d = new Date(Date.now() - 3 * 60 * 60_000).toISOString();
    expect(formatRelativeTime(d)).toBe("3 hours ago");
  });

  it("uses singular for 1 day ago", () => {
    const d = new Date(Date.now() - 24 * 60 * 60_000).toISOString();
    expect(formatRelativeTime(d)).toBe("1 day ago");
  });

  it("uses plural for 3 days ago", () => {
    const d = new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString();
    expect(formatRelativeTime(d)).toBe("3 days ago");
  });
});

describe("formatPercent", () => {
  it("formats to 1 decimal place", () => {
    expect(formatPercent(75.5)).toBe("75.5%");
    expect(formatPercent(100)).toBe("100.0%");
    expect(formatPercent(0)).toBe("0.0%");
  });
});
