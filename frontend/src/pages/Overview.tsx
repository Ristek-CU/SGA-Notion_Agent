import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';
import { StatCard } from '../components/StatCard';
import { Ticket, CheckCircle, Clock, AlertTriangle } from 'lucide-react';

export const Overview: React.FC = () => {
  const { data: overview, isLoading, isError, error } = useQuery({
    queryKey: ['overview'],
    queryFn: () => fetchApi<any>('/admin/notion/overview'),
  });

  if (isLoading) return <div className="p-4">Loading overview...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat overview: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Dashboard Overview</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard title="Total Tickets" value={overview?.total || 0} icon={Ticket} color="bg-blue-600" />
        <StatCard title="Done" value={overview?.by_status?.Done || 0} icon={CheckCircle} color="bg-emerald-600" />
        <StatCard title="In Progress" value={overview?.by_status?.['In Progress'] || 0} icon={Clock} color="bg-amber-600" />
        <StatCard title="Backlog" value={overview?.by_status?.Backlog || 0} icon={AlertTriangle} color="bg-slate-600" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Tickets by Division</h2>
          {Object.entries(overview?.by_division || {}).length === 0 ? (
            <p className="text-sm text-slate-400">Belum ada data.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(overview?.by_division || {}).map(([div, count]) => (
                <div key={div} className="flex justify-between items-center pb-2 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-700">{div}</span>
                  <span className="text-sm font-bold text-slate-900">{count as number}</span>
                </div>
              ))}
            </div>
          )}

        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Tickets by Status</h2>
          {Object.entries(overview?.by_status || {}).length === 0 ? (
            <p className="text-sm text-slate-400">Belum ada data.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(overview?.by_status || {}).map(([status, count]) => (
                <div key={status} className="flex justify-between items-center pb-2 border-b border-slate-100">
                  <span className="text-sm font-medium text-slate-700">{status}</span>
                  <span className="text-sm font-bold text-slate-900">{count as number}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
