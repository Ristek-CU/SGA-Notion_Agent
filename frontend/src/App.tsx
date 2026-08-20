import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Overview } from './pages/Overview';
import { Tickets } from './pages/Tickets';
import { WA } from './pages/WA';
import { Members } from './pages/Members';
import { Broadcast } from './pages/Broadcast';
import { Session } from './pages/Session';
import { Guard } from './pages/Guard';
import { Config } from './pages/Config';
import { Audit } from './pages/Audit';
import { getToken } from './api/client';

const queryClient = new QueryClient();

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = getToken();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Overview />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="wa" element={<WA />} />
            <Route path="members" element={<Members />} />
            <Route path="broadcast" element={<Broadcast />} />
            <Route path="sessions" element={<Session />} />
            <Route path="guard" element={<Guard />} />
            <Route path="config" element={<Config />} />
            <Route path="audit" element={<Audit />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
