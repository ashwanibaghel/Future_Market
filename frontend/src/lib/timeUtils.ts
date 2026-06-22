/**
 * timeUtils.ts
 * Centralised IST timezone helpers.
 *
 * WHY: Backend stores timestamps with datetime.utcnow() — these come
 * over the wire WITHOUT a trailing 'Z' or '+00:00'. Browsers that
 * do not see a timezone suffix parse the string as *local time*, which
 * produces a 5h30m offset for users in IST. The fix is to always append
 * 'Z' before constructing a Date, then format explicitly in Asia/Kolkata.
 */

const IST = "Asia/Kolkata";

/**
 * Parse a backend UTC timestamp string to a Date.
 * Appends 'Z' if no timezone info is present.
 */
export function parseUTC(isoString: string | null | undefined): Date | null {
  if (!isoString) return null;
  const s = isoString.trim();
  // Already has timezone info
  if (s.endsWith("Z") || s.includes("+") || /\d{2}:\d{2}:\d{2}-\d{2}/.test(s)) {
    return new Date(s);
  }
  // Treat as UTC
  return new Date(s + "Z");
}

/** Format to IST time string — e.g. "13:24" */
export function formatIST(
  isoString: string | null | undefined,
  opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", hour12: false }
): string {
  const d = parseUTC(isoString);
  if (!d || isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-IN", { ...opts, timeZone: IST });
}

/** Format to IST date string — e.g. "22 Jun" */
export function formatISTDate(
  isoString: string | null | undefined,
  opts: Intl.DateTimeFormatOptions = { day: "2-digit", month: "short" }
): string {
  const d = parseUTC(isoString);
  if (!d || isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-IN", { ...opts, timeZone: IST });
}

/** Format to full IST datetime — e.g. "22 Jun, 13:24:05" */
export function formatISTFull(isoString: string | null | undefined): string {
  const d = parseUTC(isoString);
  if (!d || isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: IST,
  });
}

/** "X seconds/minutes ago" relative label using IST-aware diff */
export function relativeIST(isoString: string | null | undefined): string {
  const d = parseUTC(isoString);
  if (!d || isNaN(d.getTime())) return "—";
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return `${Math.floor(diffSec / 3600)}h ago`;
}
