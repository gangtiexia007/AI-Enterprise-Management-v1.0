const BASE = '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${method} ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

export const api = {
  get: <T = unknown>(path: string) => request<T>('GET', path),
  post: <T = unknown>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T = unknown>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del: <T = unknown>(path: string) => request<T>('DELETE', path),
};

/* ---------- Tasks ---------- */

export interface Task {
  id: number;
  title: string;
  description?: string;
  assignee_name?: string;
  assignee_id?: number;
  deadline?: string;
  priority?: 'normal' | 'high' | 'urgent';
  status?: string;
  goal_id?: number;
  created_at?: string;
  updated_at?: string;
}

export const getTasks = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return api.get<Task[]>(`/tasks${qs}`);
};
export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`);
export const createTask = (data: Partial<Task>) => api.post<Task>('/tasks', data);
export const updateTask = (id: number, data: Partial<Task>) => api.put<Task>(`/tasks/${id}`, data);
export const deleteTask = (id: number) => api.del(`/tasks/${id}`);
export const dispatchTask = (id: number) => api.post(`/tasks/${id}/dispatch`);

/* ---------- Goals ---------- */

export interface Goal {
  id: number;
  title: string;
  level?: 'company' | 'department' | 'individual';
  owner?: string;
  target_value?: number;
  current_value?: number;
  unit?: string;
  deadline?: string;
  status?: string;
  parent_id?: number | null;
  children?: Goal[];
  progress?: number;
  created_at?: string;
}

export const getGoals = () => api.get<Goal[]>('/goals');
export const getGoal = (id: number) => api.get<Goal>(`/goals/${id}`);
export const createGoal = (data: Partial<Goal>) => api.post<Goal>('/goals', data);
export const updateGoal = (id: number, data: Partial<Goal>) => api.put<Goal>(`/goals/${id}`, data);
export const deleteGoal = (id: number) => api.del(`/goals/${id}`);

/* ---------- KPI ---------- */

export interface KPIRecord {
  id: number;
  employee_name?: string;
  employee_id?: number;
  metric_name?: string;
  target_value?: number;
  actual_value?: number;
  score?: number;
  grade?: string;
  weight?: number;
  period?: string;
  ai_comment?: string;
  created_at?: string;
}

export interface KPISummary {
  employee_id: number;
  employee_name: string;
  avg_score: number;
  record_count: number;
}

export const getKPIs = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return api.get<KPIRecord[]>(`/kpi${qs}`);
};
export const getKPISummary = () => api.get<KPISummary[]>('/kpi/summary');
export const createKPI = (data: Partial<KPIRecord>) => api.post<KPIRecord>('/kpi', data);
export const updateKPI = (id: number, data: Partial<KPIRecord>) => api.put<KPIRecord>(`/kpi/${id}`, data);
export const deleteKPI = (id: number) => api.del(`/kpi/${id}`);

/* ---------- Knowledge ---------- */

export interface KnowledgeItem {
  id: number;
  title: string;
  category?: 'sop' | 'case' | 'rule' | 'taboo';
  content?: string;
  source?: string;
  created_at?: string;
  updated_at?: string;
}

export const getKnowledge = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return api.get<KnowledgeItem[]>(`/knowledge${qs}`);
};
export const getKnowledgeItem = (id: number) => api.get<KnowledgeItem>(`/knowledge/${id}`);
export const createKnowledge = (data: Partial<KnowledgeItem>) => api.post<KnowledgeItem>('/knowledge', data);
export const updateKnowledge = (id: number, data: Partial<KnowledgeItem>) =>
  api.put<KnowledgeItem>(`/knowledge/${id}`, data);
export const deleteKnowledge = (id: number) => api.del(`/knowledge/${id}`);

/* ---------- Employees ---------- */

export interface Employee {
  id: number;
  name: string;
  department?: string;
  position?: string;
  feishu_id?: string;
  created_at?: string;
}

export const getEmployees = () => api.get<Employee[]>('/employees');
export const getEmployee = (id: number) => api.get<Employee>(`/employees/${id}`);
export const createEmployee = (data: Partial<Employee>) => api.post<Employee>('/employees', data);
export const updateEmployee = (id: number, data: Partial<Employee>) =>
  api.put<Employee>(`/employees/${id}`, data);
export const deleteEmployee = (id: number) => api.del(`/employees/${id}`);

/* ---------- Approvals ---------- */

export interface Approval {
  id: number;
  type: string;
  title: string;
  detail?: string;
  priority?: number;
  status: string;
  created_at?: string;
  resolved_at?: string;
  resolved_by?: string;
}

export const getApprovals = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return api.get<Approval[]>(`/approvals${qs}`);
};
export const approveApproval = (id: number) => api.post(`/approvals/${id}/approve`);
export const rejectApproval = (id: number, reason?: string) =>
  api.post(`/approvals/${id}/reject`, { reason });

/* ---------- Audit Logs ---------- */

export interface AuditLogEntry {
  id: number;
  action: string;
  detail?: string;
  actor?: string;
  resource_type?: string;
  resource_id?: string;
  created_at?: string;
}

export const getAuditLogs = (params?: Record<string, string>) => {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return api.get<AuditLogEntry[]>(`/audit-logs${qs}`);
};

/* ---------- Coaching ---------- */

export interface CoachingRecord {
  id: number;
  employee_id: number;
  type: string;
  content: string;
  ai_suggestion?: string;
  created_at?: string;
}

export const getCoachingRecords = (employeeId: number) =>
  api.get<CoachingRecord[]>(`/coaching?employee_id=${employeeId}`);
export const createCoachingRecord = (data: Partial<CoachingRecord>) =>
  api.post<CoachingRecord>('/coaching', data);

/* ---------- Settings ---------- */

export interface Setting {
  id?: number;
  key: string;
  value: string;
}

export const getSettings = () => api.get<Setting[]>('/settings');
export const updateSetting = (data: { key: string; value: string }) =>
  api.put<Setting>('/settings', data);
export const initSettings = () => api.post('/settings/init');

/* ---------- Reports ---------- */

export interface Stats {
  total_tasks: number;
  overdue_tasks: number;
  pending_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  goal_progress: number;
  avg_kpi_score: number;
  knowledge_count: number;
  employee_count: number;
  pending_approvals: number;
}

export const getStats = () => api.get<Stats>('/reports/stats');
export const getDailyReport = () => api.get('/reports/daily');
export const getTokenUsage = () => api.get('/reports/token-usage');

/* ---------- Agent ---------- */

export interface ChatMessage {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
}

export const chatWithAgent = (content: string) =>
  api.post<ChatMessage>('/agent/chat', { content });
export const getAgentHistory = () => api.get<ChatMessage[]>('/agent/history');
