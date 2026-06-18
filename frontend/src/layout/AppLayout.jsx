import { useState } from "react";
import { Outlet } from "react-router-dom";
import MobileSidebar from "./MobileSidebar";
import Sidebar from "./Sidebar";

function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-brew-cream text-brew-brown">
      <div className="flex min-h-screen">
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((value) => !value)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="hidden">
            <MobileSidebar open={mobileOpen} onOpenChange={setMobileOpen} />
            <div className="ml-3 flex items-center gap-2 text-sm font-semibold text-brew-brown">
              <span className="grid h-8 w-8 place-items-center rounded-md bg-brew-brown text-xs text-brew-foam">BC</span>
              BrewCo CRM
            </div>
          </div>

          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-7xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

export default AppLayout;
