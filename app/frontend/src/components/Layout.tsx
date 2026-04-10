import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, ListTodo, Target, BarChart3, BookOpen, Settings, Users, CheckCircle, FileText, Menu, MessageCircle, Bot, Database } from 'lucide-react';
import ChatDrawer from './ChatDrawer';

const NAV_GROUPS = [
  {
    group: '管理中心',
    links: [
      { to: '/', label: '总览', icon: LayoutDashboard },
      { to: '/tasks', label: '任务管理', icon: ListTodo },
      { to: '/goals', label: '目标管理', icon: Target },
      { to: '/approvals', label: '审批中心', icon: CheckCircle },
    ],
  },
  {
    group: '数据分析',
    links: [
      { to: '/kpi', label: 'KPI 绩效', icon: BarChart3 },
      { to: '/data-center', label: '数据中心', icon: Database },
      { to: '/employees', label: '员工管理', icon: Users },
    ],
  },
  {
    group: 'Agent 系统',
    links: [
      { to: '/agent', label: 'Agent 管理', icon: Bot },
    ],
  },
  {
    group: '知识与系统',
    links: [
      { to: '/knowledge', label: '知识库', icon: BookOpen },
      { to: '/audit-logs', label: '审计日志', icon: FileText },
      { to: '/settings', label: '系统设置', icon: Settings },
    ],
  },
];

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const location = useLocation();

  const currentPageTitle = () => {
    for (const g of NAV_GROUPS) {
      for (const l of g.links) {
        if (l.to === location.pathname || (l.to !== '/' && location.pathname.startsWith(l.to))) return l.label;
      }
    }
    return '总览';
  };

  return (
    <div className="flex h-screen bg-surface-0 text-txt-1 antialiased">
      <aside className={`flex flex-col border-r border-border bg-surface-1 transition-all duration-200 ${sidebarOpen ? 'w-52' : 'w-0 overflow-hidden'}`}>
        <div className="flex h-12 items-center px-4 border-b border-border-subtle">
          <span className="text-sm font-semibold text-accent tracking-tight">千方百计AI</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4 scrollbar-thin">
          {NAV_GROUPS.map((group) => (
            <div key={group.group}>
              <div className="px-3 py-1 text-[10px] uppercase tracking-[0.08em] text-txt-4 font-medium">{group.group}</div>
              {group.links.map((link) => (
                <NavLink key={link.to} to={link.to} end={link.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 rounded-btn px-3 py-1.5 text-[13px] font-medium transition-colors ${
                      isActive ? 'bg-accent-soft text-accent' : 'text-txt-3 hover:bg-surface-3 hover:text-txt-2'
                    }`
                  }>
                  <link.icon className="w-4 h-4 flex-shrink-0" />
                  {link.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-border-subtle px-3 py-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-7 w-7 rounded-full bg-accent-soft text-accent flex items-center justify-center text-[11px] font-semibold flex-shrink-0">老</div>
            <div className="min-w-0">
              <div className="text-[13px] font-medium text-txt-1 truncate">老板</div>
              <div className="text-[11px] text-txt-4">管理员</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex h-12 items-center justify-between border-b border-border bg-surface-1 px-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-txt-4 hover:text-txt-2 transition-colors">
              <Menu className="w-4 h-4" />
            </button>
            <h1 className="text-[14px] font-medium text-txt-1 tracking-tight">{currentPageTitle()}</h1>
          </div>
          <button onClick={() => setChatOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 text-[13px] text-accent border border-border rounded-btn hover:bg-accent-soft transition-colors">
            <MessageCircle className="w-3.5 h-3.5" />
            AI 对话
          </button>
        </header>
        <main className="flex-1 overflow-y-auto p-5 scrollbar-thin">
          <Outlet />
        </main>
      </div>

      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
