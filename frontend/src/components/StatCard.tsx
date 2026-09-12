import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  color?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, color = 'bg-indigo-500' }) => {
  return (
    <div className="bg-white p-4 sm:p-6 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
      <div className="min-w-0 pr-2">
        <p className="text-xs sm:text-sm font-medium text-slate-500 truncate">{title}</p>
        <p className="text-xl sm:text-2xl font-bold text-slate-900 mt-0.5 sm:mt-1">{value}</p>
      </div>
      <div className={`p-2.5 sm:p-3 rounded-lg text-white shrink-0 ${color}`}>
        <Icon size={20} className="sm:w-6 sm:h-6" />
      </div>
    </div>
  );
};
