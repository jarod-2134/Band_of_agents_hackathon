import { useEffect } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { GitBranch, LayoutDashboard, Settings, BarChart3, History } from 'lucide-react';
import { NavLink } from 'react-router-dom';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { connectWebSocket, disconnectWebSocket, isConnected } = useAgentStore();

  useEffect(() => {
    // Generate a mock repo ID for demonstration
    const repoId = "demo-repo-" + Math.floor(Math.random() * 1000);
    connectWebSocket(repoId);
    return () => disconnectWebSocket();
  }, [connectWebSocket, disconnectWebSocket]);

  return (
    <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
      {/* Header */}
      <header className="h-12 border-b border-border flex items-center px-4 justify-between bg-white shrink-0 z-10 relative">
        <NavLink to="/" className="flex items-center gap-2 font-bold tracking-tight hover:opacity-80 transition-opacity">
          <GitBranch className="w-5 h-5 text-indigo-600" />
          <span>Band AI Control Plane</span>
        </NavLink>
        <div className="flex items-center gap-2 text-sm">
          <div className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-muted-foreground font-mono">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </header>

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Global Navigation Sidebar */}
        <div className="w-16 border-r border-border bg-neutral-50 flex flex-col items-center py-4 gap-4 z-10 shrink-0">
          <NavLink 
            to="/dashboard"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-indigo-100 text-indigo-600' : 'text-muted-foreground hover:bg-neutral-200 hover:text-foreground'}`
            }
            title="Dashboard"
          >
            <LayoutDashboard className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/analytics"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-indigo-100 text-indigo-600' : 'text-muted-foreground hover:bg-neutral-200 hover:text-foreground'}`
            }
            title="Analytics"
          >
            <BarChart3 className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/history"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-indigo-100 text-indigo-600' : 'text-muted-foreground hover:bg-neutral-200 hover:text-foreground'}`
            }
            title="Task History"
          >
            <History className="w-5 h-5" />
          </NavLink>

          <div className="flex-1" />

          <NavLink 
            to="/settings"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-indigo-100 text-indigo-600' : 'text-muted-foreground hover:bg-neutral-200 hover:text-foreground'}`
            }
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </NavLink>
        </div>

        {/* Page Content */}
        <div className="flex-1 flex flex-col overflow-hidden bg-secondary/10">
          {children}
        </div>
        
      </div>
    </div>
  );
}
