import { X } from "lucide-react";

function Drawer({ open, title, description, children, footer, onClose }) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 top-0 z-50 m-0 p-0">
      <button
        type="button"
        className="fixed inset-0 top-0 z-0 m-0 cursor-default bg-brew-espresso/35 p-0"
        onClick={onClose}
        aria-label="Close drawer overlay"
      />
      <section className="fixed right-0 top-0 bottom-0 z-10 m-0 flex h-screen w-full max-w-[400px] flex-col overflow-hidden rounded-l-xl bg-[#f5f0eb] p-0 shadow-[0_4px_24px_rgba(0,0,0,0.18)] sm:border-l sm:border-brew-brown/10">
        <header className="flex items-start justify-between gap-4 border-b border-brew-brown/10 px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-brew-brown">{title}</h2>
            {description && <p className="mt-1 text-sm leading-6 text-brew-roast">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-brew-roast transition hover:bg-brew-cream hover:text-brew-brown focus:outline-none focus:ring-2 focus:ring-brew-amber/40"
            aria-label="Close drawer"
          >
            <X size={19} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">{children}</div>

        {footer && <footer className="border-t border-brew-brown/10 px-5 py-4">{footer}</footer>}
      </section>
    </div>
  );
}

export default Drawer;
