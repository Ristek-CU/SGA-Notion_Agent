import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar, navItems } from './Sidebar';
import { Menu, Bell } from 'lucide-react';

export const Layout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  // Find active route label for mobile top bar
  const currentNav = navItems.find((item) => {
    if (item.path === '/') return location.pathname === '/';
    return location.pathname.startsWith(item.path);
  });

  return (
    <div className="flex min-h-screen bg-slate-50 antialiased overflow-x-hidden">
      {/* Responsive Sidebar (desktop sticky, mobile drawer) */}
      <Sidebar isOpen={mobileMenuOpen} onClose={() => setMobileMenuOpen(false)} />

      {/* Main Content Area: min-w-0 ensures flex child won't expand past 100vw */}
      <div className="flex-1 min-w-0 flex flex-col min-h-screen">
        {/* Mobile Top Header (hidden on md+) */}
        <header className="md:hidden sticky top-0 z-30 flex items-center justify-between px-3 py-2.5 bg-slate-900 text-white border-b border-slate-800 shadow-sm">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer shrink-0"
              aria-label="Buka menu navigasi"
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center font-bold text-xs text-white shrink-0">
                N
              </div>
              <span className="font-semibold text-xs sm:text-sm text-slate-100 truncate">
                {currentNav?.label || 'Notion Agent'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              Roro
            </span>
          </div>
        </header>

        {/* Content Body: fluid padding (p-3 on narrow screens, p-4 on sm, p-6 on md+) */}
        <main className="flex-1 p-3 sm:p-5 md:p-6 lg:p-8 min-w-0 w-full overflow-x-hidden">
          <div className="max-w-7xl mx-auto w-full min-w-0">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
