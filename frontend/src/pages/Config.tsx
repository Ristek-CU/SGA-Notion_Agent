import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Config: React.FC = () => {
  const { data: config, isLoading, isError, error } = useQuery({
    queryKey: ['config'],
    queryFn: () => fetchApi<any>('/admin/system/env'),
  });

  if (isLoading) return <div className="p-4">Loading config...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat config: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">App Configuration</h1>
      <div className="bg-white p-6 rounded-xl border border-slate-200">
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(config || {}, null, 2)}
        </pre>
      </div>
    </div>
  );
};
