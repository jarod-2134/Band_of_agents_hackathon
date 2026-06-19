import { useEffect } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { GitBranch, LayoutDashboard, Settings, BarChart3, History, Network, Bot } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { RepoSelector } from './RepoSelector';
import { ConflictResolver } from './ConflictResolver';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { fetchRepos, disconnectWebSocket, conflictFiles } = useAgentStore();

  useEffect(() => {
    fetchRepos();
    return () => disconnectWebSocket();
  }, [fetchRepos, disconnectWebSocket]);

  return (
    <div className="h-screen w-screen flex flex-col bg-background text-foreground overflow-hidden">
      {/* Header */}
      <header className="h-12 border-b border-border flex items-center px-4 justify-between bg-card shrink-0 z-10 relative">
        <NavLink to="/" className="flex items-center gap-2 font-bold tracking-tight hover:opacity-80 transition-opacity">
          <GitBranch className="w-5 h-5 text-primary" />
          <span>Band AI Control Plane</span>
        </NavLink>
        <RepoSelector />
      </header>

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Global Navigation Sidebar */}
        <div className="w-16 border-r border-border bg-card flex flex-col items-center py-4 gap-4 z-10 shrink-0">
          <NavLink 
            to="/dashboard"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="Dashboard"
          >
            <LayoutDashboard className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/analytics"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="Analytics"
          >
            <BarChart3 className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/history"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="Task History"
          >
            <History className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/graph"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="AST Graph"
          >
            <Network className="w-5 h-5" />
          </NavLink>

          <NavLink 
            to="/agents"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="Agent Fleet Manager"
          >
            <Bot className="w-5 h-5" />
          </NavLink>

          <div className="flex-1" />

          <NavLink 
            to="/settings"
            className={({ isActive }) => 
              `p-3 rounded-lg flex items-center justify-center transition-colors ${isActive ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-secondary hover:text-foreground'}`
            }
            title="Settings"
          >
            <Settings className="w-5 h-5" />
          </NavLink>
        </div>

        {/* Page Content */}
        <div className="flex-1 flex flex-col overflow-hidden bg-background relative">
          {conflictFiles && conflictFiles.length > 0 ? <ConflictResolver /> : children}
        </div>
        
      </div>
    </div>
  );
}
