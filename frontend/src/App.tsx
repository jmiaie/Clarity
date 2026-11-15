import type { ReactElement } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Layout from './Layout';
import Account from './pages/Account';
import Assessment from './pages/Assessment';
import Calendar from './pages/Calendar';
import Dashboard from './pages/Dashboard';
import Insights from './pages/Insights';
import Journal from './pages/Journal';
import Login from './pages/Login';
import Signup from './pages/Signup';
import './App.css';

function LoadingScreen() {
  return (
    <div className="loading-container">
      <div className="spinner"></div>
      <p>Loading...</p>
    </div>
  );
}

function PrivateRoute({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  return user ? <Layout>{children}</Layout> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  return user ? <Navigate to="/dashboard" replace /> : children;
}

const PRIVATE_PAGES: Array<{ path: string; page: ReactElement }> = [
  { path: '/dashboard', page: <Dashboard /> },
  { path: '/journal', page: <Journal /> },
  { path: '/calendar', page: <Calendar /> },
  { path: '/insights', page: <Insights /> },
  { path: '/assessment', page: <Assessment /> },
  { path: '/account', page: <Account /> },
];

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />
          {PRIVATE_PAGES.map(({ path, page }) => (
            <Route key={path} path={path} element={<PrivateRoute>{page}</PrivateRoute>} />
          ))}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
