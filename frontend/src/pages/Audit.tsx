import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Audit: React.FC = () => {
  const { data: logs } = useQuery({
    queryKey: ['audit-ai'],
    queryFn: () => fetchApi<any[]>('/admin/logs/ai'),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Audit Logs</h1>
      <div className="bg-white p-6 rounded-xl border border-slate-200">
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(logs || [], null, 2)}
        </pre>
      </div>
    </div>
  );
};
