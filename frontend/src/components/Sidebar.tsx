import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { removeToken } from '../api/client';
import { 
  LayoutDashboard, 
  Ticket, 
  MessageSquare, 
  Users, 
  Send, 
  History, 
  ShieldAlert, 
  Settings, 
  FileText, 
  LogOut 
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/tickets', label: 'Tickets', icon: Ticket },
  { path: '/wa', label: 'WA Connection', icon: MessageSquare },
  { path: '/members', label: 'Members', icon: Users },
  { path: '/broadcast', label: 'Broadcast', icon: Send },
  { path: '/sessions', label: 'Sessions', icon: History },
  { path: '/guard', label: 'Guard Rules', icon: ShieldAlert },
  { path: '/config', label: 'Config', icon: Settings },
  { path: '/audit', label: 'Audit Logs', icon: FileText },
];

export const Sidebar: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    removeToken();
    navigate('/login');
  };

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col h-screen sticky top-0">
      <div className="p-6 border-b border-slate-800 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white">N</div>
        <span className="font-semibold text-lg text-white">Notion Agent</span>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive 
                    ? 'bg-indigo-600 text-white' 
                    : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
                }`
              }
            >
              <Icon size={18} />
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-slate-800">
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full px-4 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:bg-slate-800 transition-colors"
        >
          <LogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
};
