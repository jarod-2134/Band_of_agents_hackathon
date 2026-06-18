import { useState, useEffect } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { Code2, Save, Loader2 } from 'lucide-react';

type DiffData = {
  filePath: string;
  original: string;
  modified: string;
};

type DiffViewerProps = {
  diff: DiffData;
};

export function DiffViewer({ diff }: DiffViewerProps) {
  const currentOrgSlug = useAgentStore((state) => state.currentOrgSlug);
  const currentRepoId = useAgentStore((state) => state.currentRepoId);
  
  const [content, setContent] = useState(diff.modified);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setContent(diff.modified);
  }, [diff]);

  const handleSave = async () => {
    if (!currentOrgSlug || !currentRepoId) return;
    setIsSaving(true);
    try {
      const r = await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos`);
      const data = await r.json();
      const repo = data.repositories?.find((r: any) => r.fs_path === currentRepoId);
      if (!repo) throw new Error("Repo not found");

      const response = await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos/${repo.id}/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          branch: 'main',
          message: `Update ${diff.filePath} via Web Editor`,
          changes: [{
            action: 'modify',
            file_path: diff.filePath,
            content: content
          }]
        })
      });

      if (!response.ok) {
        throw new Error("Failed to save");
      }
      alert('Changes saved successfully!');
    } catch (err) {
      console.error(err);
      alert('Error saving changes');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="w-full h-full bg-card border border-border rounded-lg overflow-hidden flex flex-col shadow-sm">
      <div className="px-4 py-3 bg-secondary border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-primary/10 text-primary flex items-center justify-center">
            <Code2 className="w-5 h-5" />
          </div>

          <div>
            <div className="font-mono text-sm font-bold text-foreground">{diff.filePath}</div>
            <div className="text-xs text-muted-foreground">
              Editable Workspace View
            </div>
          </div>
        </div>

        <button 
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          Commit Changes
        </button>
      </div>

      <div className="flex-1 min-h-0 bg-[#1e1e1e] p-4">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          spellCheck={false}
          className="w-full h-full bg-transparent text-gray-300 font-mono text-[13px] leading-relaxed resize-none focus:outline-none"
        />
      </div>
    </div>
  );
}