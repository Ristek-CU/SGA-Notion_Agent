import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Guard: React.FC = () => {
  const { data: guard } = useQuery({
    queryKey: ['guard'],
    queryFn: () => fetchApi<any>('/admin/guard'),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Guard Settings</h1>
      <div className="bg-white p-6 rounded-xl border border-slate-200">
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(guard || {}, null, 2)}
        </pre>
      </div>
    </div>
  );
};
