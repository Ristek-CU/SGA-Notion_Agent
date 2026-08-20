import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Members: React.FC = () => {
  const { data: contacts } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => fetchApi<any[]>('/admin/contacts'),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Members & Contacts</h1>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left text-sm text-slate-600">
          <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
            <tr>
              <th className="p-4">Name</th>
              <th className="p-4">Nickname</th>
              <th className="p-4">Phone</th>
              <th className="p-4">Division</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {contacts?.map((c: any, i: number) => (
              <tr key={i} className="hover:bg-slate-50">
                <td className="p-4 font-medium text-slate-900">{c.name}</td>
                <td className="p-4">{c.nickname}</td>
                <td className="p-4">{c.phone}</td>
                <td className="p-4">{c.division}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
