import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Audit: React.FC = () => {
  const { data: logs, isLoading, isError, error } = useQuery({
    queryKey: ['audit-ai'],
    queryFn: () => fetchApi<any[]>('/admin/system/audit-logs'),
  });

  if (isLoading) return <div className="p-4">Loading audit logs...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat audit logs: {(error as Error)?.message}</div>;

  const rows = (logs || []).map((l: any, i: number) => ({
    key: i,
    time: l?.timestamp ? new Date(l.timestamp * 1000).toLocaleString() : '-',
    user: l?.user ?? '-',
    action: l?.action ?? '-',
    details: l?.details ? JSON.stringify(l.details) : '-',
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Audit Logs</h1>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {rows.length === 0 ? (
          <p className="p-4 text-slate-400">Belum ada audit log.</p>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">Waktu</th>
                <th className="p-4">User</th>
                <th className="p-4">Aksi</th>
                <th className="p-4">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.key} className="hover:bg-slate-50">
                  <td className="p-4 whitespace-nowrap">{r.time}</td>
                  <td className="p-4">{r.user}</td>
                  <td className="p-4">{r.action}</td>
                  <td className="p-4">{r.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};