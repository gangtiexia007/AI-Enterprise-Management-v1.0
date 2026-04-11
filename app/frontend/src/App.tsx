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
import Agent from './pages/Agent';
import DataCenter from './pages/DataCenter';
import MultiAgentDashboard from './pages/MultiAgentDashboard';
import AgentAnalysis from './pages/AgentAnalysis';
import ReviewSedimentation from './pages/ReviewSedimentation';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/kpi" element={<KPI />} />
        <Route path="/data-center" element={<DataCenter />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/employees" element={<Employees />} />
        <Route path="/approvals" element={<Approvals />} />
        <Route path="/audit-logs" element={<AuditLogs />} />
        <Route path="/agent" element={<Agent />} />
        <Route path="/pod-dashboard" element={<MultiAgentDashboard />} />
        <Route path="/pod-analysis" element={<AgentAnalysis />} />
        <Route path="/pod-review" element={<ReviewSedimentation />} />
      </Route>
    </Routes>
  );
}
