import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const WA: React.FC = () => {
  const { data: instances } = useQuery({
    queryKey: ['wa-instances'],
    queryFn: () => fetchApi<any[]>('/admin/wa/instances'),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">WhatsApp Connection</h1>
      <div className="bg-white p-6 rounded-xl border border-slate-200">
        <h2 className="text-lg font-semibold mb-4">Evolution API Instances</h2>
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(instances || [], null, 2)}
        </pre>
      </div>
    </div>
  );
};
