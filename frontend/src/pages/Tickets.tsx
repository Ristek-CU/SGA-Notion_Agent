import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Tickets: React.FC = () => {
  const { data: tickets, isLoading, isError, error } = useQuery({
    queryKey: ['tickets'],
    queryFn: () => fetchApi<any[]>('/admin/notion/backlog'),
  });

  if (isLoading) return <div className="p-4">Loading tickets...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat tickets: {(error as Error)?.message}</div>;

  // Backend mengembalikan object Notion mentah -> ekstrak field dari properties
  const rows = (tickets || []).map((t: any) => ({
    id: t?.id || '',
    name: t?.properties?.Name?.title?.[0]?.plain_text ?? t?.properties?.Name?.title?.[0]?.text?.content ?? t?.id,
    status: t?.properties?.Status?.status?.name ?? '-',
    priority: t?.properties?.Priority?.select?.name ?? '-',
    division: t?.properties?.Division?.select?.name ?? '-',
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Tickets / Backlog</h1>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {rows.length === 0 ? (
          <p className="p-4 text-slate-400">Belum ada ticket.</p>
        ) : (
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
              {rows.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="p-4 font-medium text-slate-900">{t.name}</td>
                  <td className="p-4">{t.status}</td>
                  <td className="p-4">{t.priority}</td>
                  <td className="p-4">{t.division}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
