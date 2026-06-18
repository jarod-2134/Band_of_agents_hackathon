import { useState } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { Database, Plus, Trash2 } from 'lucide-react';
import { CloneRepoModal } from './CloneRepoModal';

export function RepoSelector() {
  const repos = useAgentStore((state) => state.repos);
  const currentRepoId = useAgentStore((state) => state.currentRepoId);
  const currentOrgSlug = useAgentStore((state) => state.currentOrgSlug);
  const connectWebSocket = useAgentStore((state) => state.connectWebSocket);
  const isConnected = useAgentStore((state) => state.isConnected);
  const fetchRepos = useAgentStore((state) => state.fetchRepos);
  
  const [showCloneModal, setShowCloneModal] = useState(false);

  return (
    <div className="flex items-center gap-4">
      <div className="flex items-center gap-2">
        <Database className="w-4 h-4 text-muted-foreground" />
        <select
          className="text-sm bg-background border border-border rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary/50"
          value={currentRepoId || ""}
          onChange={(e) => {
            if (e.target.value) {
              connectWebSocket(e.target.value);
            }
          }}
        >
          <option value="" disabled>Select a repository...</option>
          {repos.map((r) => (
            <option key={r.id} value={r.fs_path}>{r.name}</option>
          ))}
        </select>
        
        <button 
          onClick={() => setShowCloneModal(true)} 
          className="hover:text-primary transition-colors p-1"
          title="Clone Repository"
        >
          <Plus className="w-4 h-4 text-muted-foreground hover:text-foreground" />
        </button>
        
        {currentRepoId && (
          <button 
            onClick={() => {
              const repo = repos.find(r => r.fs_path === currentRepoId);
              if (repo && window.confirm(`Are you sure you want to delete ${repo.name}?`)) {
                fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos/${repo.id}`, { method: 'DELETE' })
                  .then(() => {
                    connectWebSocket('');
                    return fetchRepos();
                  })
                  .catch(err => console.error("Failed to delete repo", err));
              }
            }}
            className="text-muted-foreground hover:text-destructive transition-colors p-1"
            title="Delete Repository"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 text-sm bg-card px-2 py-1 rounded-md border border-border">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className="text-muted-foreground font-mono text-xs">{isConnected ? 'Connected' : 'Disconnected'}</span>
      </div>
      
      <CloneRepoModal 
        isOpen={showCloneModal}
        onClose={() => setShowCloneModal(false)}
        onSuccess={(repoPath) => {
          connectWebSocket(repoPath);
          fetchRepos();
        }}
      />
    </div>
  );
}
