const styles = {
  sent: "bg-green-100 text-green-800 ring-green-200",
  delivered: "bg-green-100 text-green-800 ring-green-200",
  processing: "bg-amber-100 text-amber-800 ring-amber-200",
  partially_failed: "bg-amber-100 text-amber-800 ring-amber-200",
  "partially failed": "bg-amber-100 text-amber-800 ring-amber-200",
  partial: "bg-amber-100 text-amber-800 ring-amber-200",
  draft: "bg-brew-cream text-brew-roast ring-brew-brown/15",
  failed: "bg-red-100 text-red-800 ring-red-200",
  red: "bg-red-100 text-red-800 ring-red-200",
  yellow: "bg-amber-100 text-amber-800 ring-amber-200",
  green: "bg-green-100 text-green-800 ring-green-200",
  default: "bg-brew-cream text-brew-roast ring-brew-brown/15"
};

function StatusBadge({ value, children }) {
  const rawKey = String(value || "default").toLowerCase();
  const cleanKey = rawKey.replace(/_/g, " ");
  const className = styles[rawKey] || styles[cleanKey] || styles.default;
  const label = children || (value ? String(value).replace(/_/g, " ") : "Unknown");

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium capitalize ring-1 ring-inset ${className}`}>
      {label}
    </span>
  );
}

export default StatusBadge;