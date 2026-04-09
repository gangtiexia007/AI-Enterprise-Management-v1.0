import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import Tasks from './pages/Tasks';
import Goals from './pages/Goals';
import KPI from './pages/KPI';
import Knowledge from './pages/Knowledge';
import Settings from './pages/Settings';
import Employees from './pages/Employees';
import Approvals from './pages/Approvals';
import AuditLogs from './pages/AuditLogs';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/kpi" element={<KPI />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/employees" element={<Employees />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/audit-logs" element={<AuditLogs />} />
      </Route>
    </Routes>
  );
}
