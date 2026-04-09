import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, ListTodo, Target, BarChart3, BookOpen, Settings, Users, CheckCircle, FileText, Menu, MessageCircle } from 'lucide-react';
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
      { to: '/employees', label: '员工管理', icon: Users },
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
        if (l.to === location.pathname || (l.to !== '/' && location.pathname.startsWith(l.to))) {
          return l.label;
        }
      }
    }
    return '总览';
  };

  return (
    <div className="flex h-screen bg-gray-50 text-gray-800 antialiased">
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r border-gray-200 bg-white transition-all duration-200 ${
          sidebarOpen ? 'w-56' : 'w-0 overflow-hidden'
        }`}
      >
        <div className="flex h-14 items-center border-b border-gray-200 px-4">
          <span className="text-base font-semibold text-brand-700 tracking-tight">千方百计AI</span>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4 scrollbar-thin">
          {NAV_GROUPS.map((group) => (
            <div key={group.group}>
              <div className="nav-group-title px-3 py-1 text-gray-400 uppercase font-medium">
                {group.group}
              </div>
              {group.links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) =>
                    `sidebar-link flex items-center gap-2.5 rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 ${
                      isActive ? 'active' : ''
                    }`
                  }
                >
                  <link.icon className="w-4 h-4" />
                  {link.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="border-t border-gray-200 px-3 py-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <div className="h-7 w-7 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
                老
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">老板</div>
                <div className="text-xs text-gray-400">管理员</div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="text-gray-400 hover:text-gray-600">
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-base font-semibold text-gray-700">{currentPageTitle()}</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-brand-600 border border-brand-200 rounded-md hover:bg-brand-50"
            >
              <MessageCircle className="w-4 h-4" />
              AI 对话
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      <ChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  );
}
