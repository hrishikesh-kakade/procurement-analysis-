export const money = (value: any) =>
  value === null || value === undefined || value === ""
    ? "—"
    : new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value));

export const shortDate = (value?: string | null) =>
  value ? new Date(value).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const percent = (value: any) => (value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`);

export const label = (value?: string | null) => (value ? value.replace(/_/g, " ") : "—");

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
