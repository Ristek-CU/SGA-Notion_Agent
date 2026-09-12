import React from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { removeToken } from '../api/client';
import { 
  LayoutDashboard, 
  Ticket,
  Users, 
  Send, 
  Layers,
  History, 
  ShieldAlert, 
  Settings,
  FileText,
  Bot,
  LogOut,
  X
} from 'lucide-react';

export const navItems = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/tickets', label: 'Tickets', icon: Ticket },
  { path: '/members', label: 'Members', icon: Users },
  { path: '/broadcast', label: 'Broadcast', icon: Send },
  { path: '/queues', label: 'Queue Monitor', icon: Layers },
  { path: '/sessions', label: 'Sessions', icon: History },
  { path: '/guard', label: 'Guard Rules', icon: ShieldAlert },
  { path: '/config', label: 'Config', icon: Settings },
  { path: '/platforms', label: 'Platforms', icon: Bot },
  { path: '/audit', label: 'Audit Logs', icon: FileText },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    removeToken();
    if (onClose) onClose();
    navigate('/login');
  };

  const handleNavClick = () => {
    if (onClose) onClose();
  };

  const sidebarContent = (
    <div className="flex flex-col h-full bg-slate-900 text-slate-300 select-none">
      {/* Brand Header */}
      <div className="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-sm shadow-indigo-600/30">
            N
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-base sm:text-lg text-white leading-tight">Notion Agent</span>
            <span className="text-[10px] text-slate-400">Roro Dashboard</span>
          </div>
        </div>

        {/* Close button on mobile drawer */}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            aria-label="Tutup menu navigasi"
          >
            <X size={20} />
          </button>
        )}
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-3 py-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={handleNavClick}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs sm:text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-indigo-600 text-white shadow-xs' 
                    : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                }`
              }
            >
              <Icon size={18} className="shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Logout Footer */}
      <div className="p-3 sm:p-4 border-t border-slate-800">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-3.5 py-2.5 rounded-lg text-xs sm:text-sm font-medium text-red-400 hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <LogOut size={18} className="shrink-0" />
          <span className="truncate">Logout</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar (md+) */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col h-screen sticky top-0 border-r border-slate-800 z-20">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer (screens < md) */}
      <div
        className={`fixed inset-0 z-50 md:hidden transition-all duration-300 ${
          isOpen ? 'pointer-events-auto visible' : 'pointer-events-none invisible'
        }`}
      >
        {/* Backdrop overlay */}
        <div
          onClick={onClose}
          className={`absolute inset-0 bg-slate-950/70 backdrop-blur-xs transition-opacity duration-300 ${
            isOpen ? 'opacity-100' : 'opacity-0'
          }`}
        />

        {/* Drawer slide-over */}
        <div
          className={`absolute top-0 left-0 bottom-0 w-72 max-w-[85vw] bg-slate-900 shadow-2xl transition-transform duration-300 transform flex flex-col ${
            isOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          {sidebarContent}
        </div>
      </div>
    </>
  );
};
