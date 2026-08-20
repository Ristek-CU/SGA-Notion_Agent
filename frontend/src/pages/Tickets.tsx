import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Tickets: React.FC = () => {
  const { data: tickets, isLoading } = useQuery({
    queryKey: ['tickets'],
    queryFn: () => fetchApi<any[]>('/admin/backlog'),
  });

  if (isLoading) return <div className="p-4">Loading tickets...</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Tickets / Backlog</h1>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <table className="w-full text-left text-sm text-slate-600">
          <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
            <tr>
              <th className="p-4">Task Name</th>
              <th className="p-4">Status</th>
              <th className="p-4">Priority</th>
              <th className="p-4">Division</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tickets?.map((t: any) => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="p-4 font-medium text-slate-900">{t.name || t.id}</td>
                <td className="p-4">{t.status}</td>
                <td className="p-4">{t.priority}</td>
                <td className="p-4">{t.division}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
