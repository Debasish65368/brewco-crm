import { Coffee } from "lucide-react";

function EmptyState({ icon: Icon = Coffee, title = "Nothing here yet", description, action }) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center rounded-lg border border-dashed border-brew-brown/20 bg-brew-foam px-6 py-10 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-brew-cream text-brew-amber">
        <Icon size={24} />
      </div>
      <h2 className="mt-4 text-base font-semibold text-brew-brown">{title}</h2>
      {description && <p className="mt-2 max-w-md text-sm leading-6 text-brew-roast">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export default EmptyState;