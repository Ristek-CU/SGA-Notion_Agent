import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Members: React.FC = () => {
  const { data: contacts, isLoading, isError, error } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => fetchApi<any[]>('/admin/contacts'),
  });

  if (isLoading) return <div className="p-4">Loading contacts...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat kontak: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Members & Contacts</h1>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {(contacts || []).length === 0 ? (
          <p className="p-4 text-slate-400">Belum ada kontak. (Backend membaca dari <code>config/contacts.json</code>)</p>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">Name</th>
                <th className="p-4">Nickname</th>
                <th className="p-4">Phone</th>
                <th className="p-4">Role</th>
                <th className="p-4">Division</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(contacts || []).map((c: any, i: number) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="p-4 font-medium text-slate-900">{c.name}</td>
                  <td className="p-4">{c.nickname || '-'}</td>
                  <td className="p-4">{c.phone}</td>
                  <td className="p-4">{c.role || '-'}</td>
                  <td className="p-4">{c.division || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
