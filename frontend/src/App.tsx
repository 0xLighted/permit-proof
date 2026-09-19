import React, { useState, useEffect } from 'react';
import { TechnicianDashboard } from './pages/TechnicianDashboard';
import { SupervisorDashboard } from './pages/SupervisorDashboard';
import { LauncherPage } from './pages/LauncherPage';

export const App: React.FC = () => {
  const determineRole = (): 'technician' | 'supervisor' | 'launcher' => {
    const port = window.location.port;
    if (port === '1501') return 'technician';
    if (port === '1502') return 'supervisor';

    const path = window.location.pathname.toLowerCase();
    if (path.startsWith('/technician')) return 'technician';
    if (path.startsWith('/supervisor')) return 'supervisor';

    return 'launcher';
  };

  const [role, setRole] = useState<'technician' | 'supervisor' | 'launcher'>(determineRole);

  useEffect(() => {
    const handleLocationChange = () => {
      setRole(determineRole());
    };

    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);

  if (role === 'technician') {
    return <TechnicianDashboard />;
  }

  if (role === 'supervisor') {
    return <SupervisorDashboard />;
  }

  return <LauncherPage />;
};

export default App;
