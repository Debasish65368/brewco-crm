import { BarChart3, Megaphone, Menu, Users, Waypoints, X } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { label: "Dashboard", path: "/", icon: BarChart3 },
  { label: "Customers", path: "/customers", icon: Users },
  { label: "Segments", path: "/segments", icon: Waypoints },
  { label: "Campaigns", path: "/campaigns", icon: Megaphone }
];

function MobileSidebar({ open, onOpenChange }) {
  return (
    <>
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        className="grid h-10 w-10 place-items-center rounded-md border border-brew-brown/10 bg-brew-foam text-brew-brown shadow-sm transition hover:bg-brew-cream focus:outline-none focus:ring-2 focus:ring-brew-amber/40 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu size={20} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 cursor-default bg-brew-espresso/35"
            onClick={() => onOpenChange(false)}
            aria-label="Close navigation overlay"
          />
          <aside className="relative flex h-full w-80 max-w-[86vw] flex-col border-r border-brew-brown/10 bg-brew-foam shadow-xl">
            <div className="flex h-16 items-center justify-between border-b border-brew-brown/10 px-4">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-brew-brown text-sm font-bold text-brew-foam">
                  BC
                </div>
                <div>
                  <p className="text-sm font-semibold text-brew-brown">BrewCo CRM</p>
                  <p className="text-xs text-brew-roast">Customer growth desk</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onOpenChange(false)}
                className="grid h-9 w-9 place-items-center rounded-md text-brew-roast transition hover:bg-brew-cream hover:text-brew-brown focus:outline-none focus:ring-2 focus:ring-brew-amber/40"
                aria-label="Close navigation"
              >
                <X size={19} />
              </button>
            </div>

            <nav className="space-y-1 px-3 py-5" aria-label="Mobile navigation">
              {navItems.map((item) => {
                const Icon = item.icon;

                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === "/"}
                    onClick={() => onOpenChange(false)}
                    className={({ isActive }) =>
                      `flex h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition ${
                        isActive
                          ? "bg-brew-brown text-brew-foam shadow-sm"
                          : "text-brew-roast hover:bg-brew-cream hover:text-brew-brown"
                      }`
                    }
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          </aside>
        </div>
      )}
    </>
  );
}

export default MobileSidebar;