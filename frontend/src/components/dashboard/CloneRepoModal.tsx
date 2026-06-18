import { useState } from 'react';
import { X, GitPullRequest, Loader2 } from 'lucide-react';
import { useAgentStore } from '@/store/useAgentStore';

interface CloneRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (repoId: string) => void;
}

export function CloneRepoModal({ isOpen, onClose, onSuccess }: CloneRepoModalProps) {
  const { currentOrgSlug } = useAgentStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    repoUrl: '',
    githubToken: ''
  });

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        name: formData.name,
        repo_url: formData.repoUrl,
        github_token: formData.githubToken || null
      };

      const response = await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos/clone`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const responseData = await response.json();
      if (!response.ok) {
        throw new Error(responseData.detail || 'Failed to clone repository');
      }

      setFormData({ name: '', repoUrl: '', githubToken: '' });
      if (onSuccess) onSuccess(responseData.repo_id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg flex flex-col animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 font-semibold">
            <GitPullRequest className="w-4 h-4 text-primary" />
            Clone Repository
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 flex flex-col gap-4">
          {error && (
            <div className="text-xs p-2 rounded bg-destructive/10 text-destructive border border-destructive/20">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground">Project Name</label>
            <input 
              type="text" 
              required
              placeholder="e.g. react-demo"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="px-3 py-2 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground">Repository URL</label>
            <input 
              type="url" 
              required
              placeholder="e.g. https://github.com/facebook/react.git"
              value={formData.repoUrl}
              onChange={(e) => setFormData({ ...formData, repoUrl: e.target.value })}
              className="px-3 py-2 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-foreground">GitHub Token <span className="text-muted-foreground font-normal">(Optional)</span></label>
            <input 
              type="password" 
              placeholder="ghp_..."
              value={formData.githubToken}
              onChange={(e) => setFormData({ ...formData, githubToken: e.target.value })}
              className="px-3 py-2 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-[10px] text-muted-foreground mt-0.5">Required only for private repositories.</p>
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <button 
              type="button" 
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium rounded-md hover:bg-secondary transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button 
              type="submit" 
              disabled={loading}
              className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? 'Cloning...' : 'Clone Repository'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
