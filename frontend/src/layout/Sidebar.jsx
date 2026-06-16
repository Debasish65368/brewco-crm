import { BarChart3, Megaphone, PanelLeftClose, PanelLeftOpen, Users, Waypoints } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  { label: "Dashboard", path: "/", icon: BarChart3 },
  { label: "Customers", path: "/customers", icon: Users },
  { label: "Segments", path: "/segments", icon: Waypoints },
  { label: "Campaigns", path: "/campaigns", icon: Megaphone }
];

function Sidebar({ collapsed = false, onToggle }) {
  return (
    <aside
      className={`hidden min-h-screen border-r border-brew-brown/10 bg-brew-foam shadow-sm transition-all duration-300 lg:flex lg:flex-col ${
        collapsed ? "lg:w-20" : "lg:w-64"
      }`}
    >
      <div className="flex h-16 items-center justify-between border-b border-brew-brown/10 px-4">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-brew-brown text-sm font-bold text-brew-foam shadow-sm">
            BC
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-brew-brown">BrewCo CRM</p>
              <p className="truncate text-xs text-brew-roast">Customer growth desk</p>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="grid h-9 w-9 place-items-center rounded-md text-brew-roast transition hover:bg-brew-cream hover:text-brew-brown focus:outline-none focus:ring-2 focus:ring-brew-amber/40"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-5" aria-label="Primary navigation">
        {navItems.map((item) => {
          const Icon = item.icon;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `group flex h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition ${
                  isActive
                    ? "bg-brew-brown text-brew-foam shadow-sm"
                    : "text-brew-roast hover:bg-brew-cream hover:text-brew-brown"
                } ${collapsed ? "justify-center" : "justify-start"}`
              }
              title={collapsed ? item.label : undefined}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}

export default Sidebar;