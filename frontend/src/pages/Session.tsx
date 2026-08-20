import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Session: React.FC = () => {
  const { data: sessions } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchApi<any[]>('/admin/sessions'),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Redis Sessions</h1>
      <div className="bg-white p-6 rounded-xl border border-slate-200">
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(sessions || [], null, 2)}
        </pre>
      </div>
    </div>
  );
};
