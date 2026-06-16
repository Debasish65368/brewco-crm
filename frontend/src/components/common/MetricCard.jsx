function MetricCard({ title, value, description, icon: Icon, tone = "amber" }) {
  const tones = {
    amber: "bg-brew-amber/12 text-brew-amber",
    brown: "bg-brew-brown/10 text-brew-brown",
    sage: "bg-brew-sage/15 text-brew-sage",
    red: "bg-red-100 text-red-700"
  };

  return (
    <article className="rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-brew-roast">{title}</p>
          <p className="mt-3 truncate text-3xl font-semibold text-brew-brown">{value}</p>
        </div>
        {Icon && (
          <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-lg ${tones[tone] || tones.amber}`}>
            <Icon size={21} />
          </div>
        )}
      </div>
      {description && <p className="mt-3 text-sm leading-6 text-brew-roast">{description}</p>}
    </article>
  );
}

export default MetricCard;