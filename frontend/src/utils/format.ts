export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "Never";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);

  if (diffSeconds < 60) return "Just now";
  if (diffSeconds < 3600) {
    const m = Math.floor(diffSeconds / 60);
    return `${m} min ago`;
  }
  if (diffSeconds < 86400) {
    const h = Math.floor(diffSeconds / 3600);
    return `${h} hour${h !== 1 ? "s" : ""} ago`;
  }
  const d = Math.floor(diffSeconds / 86400);
  return `${d} day${d !== 1 ? "s" : ""} ago`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString();
}

export function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`;
}
