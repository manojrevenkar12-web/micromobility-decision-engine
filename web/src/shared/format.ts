/** Fixed decimals, a real minus sign, and an em dash for missing values. */
export function fmt(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits).replace("-", "−");
}

export function signed(v: number, digits = 1): string {
  return (v > 0 ? "+" : "") + fmt(v, digits);
}

export function thousands(v: number): string {
  return v.toLocaleString("en-GB");
}
