import { useState, useRef, useEffect } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { GitBranch, Plus, Trash2, GitMerge, ChevronDown, AlertCircle, CheckCircle2 } from 'lucide-react';

export function BranchSelector() {
  const currentRepoId = useAgentStore((state) => state.currentRepoId);
  const branches = useAgentStore((state) => state.branches);
  const currentBranch = useAgentStore((state) => state.currentBranch);
  const setCurrentBranch = useAgentStore((state) => state.setCurrentBranch);
  const createBranch = useAgentStore((state) => state.createBranch);
  const deleteBranch = useAgentStore((state) => state.deleteBranch);
  const mergeBranch = useAgentStore((state) => state.mergeBranch);

  const [isOpen, setIsOpen] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [targetBranchName, setTargetBranchName] = useState('');
  const [confirmState, setConfirmState] = useState<'none' | 'merge' | 'delete'>('none');
  const [statusMessage, setStatusMessage] = useState<{text: string, type: 'error'|'success'} | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setConfirmState('none');
        setStatusMessage(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!currentRepoId) return null;

  const showStatus = (text: string, type: 'error'|'success') => {
    setStatusMessage({text, type});
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const handleCreate = async () => {
    if (newBranchName) {
      try {
        await createBranch(newBranchName.trim(), currentBranch);
        setNewBranchName('');
        setConfirmState('none');
        showStatus('Branch created', 'success');
      } catch (e: any) {
        showStatus(e.message || 'Failed to create branch', 'error');
      }
    }
  };

  const executeMerge = async () => {
    if (targetBranchName) {
      try {
        await mergeBranch(currentBranch, targetBranchName.trim());
        setTargetBranchName('');
        setConfirmState('none');
        showStatus('Merge successful', 'success');
      } catch (e: any) {
        setConfirmState('none');
        showStatus(e.message || 'Merge failed', 'error');
      }
    }
  };

  const executeDelete = async () => {
    try {
      await deleteBranch(currentBranch);
      setConfirmState('none');
      showStatus('Branch deleted', 'success');
    } catch (e: any) {
      setConfirmState('none');
      showStatus(e.message || 'Failed to delete branch', 'error');
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-sm bg-background border border-border rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary/50 hover:bg-secondary transition-colors"
      >
        <GitBranch className="w-4 h-4 text-muted-foreground" />
        <span>{currentBranch}</span>
        <ChevronDown className="w-3 h-3 text-muted-foreground ml-1" />
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-1 w-64 bg-card border border-border rounded-md shadow-lg z-50 p-2 flex flex-col gap-3">
          
          {statusMessage && (
            <div className={`flex items-center gap-2 text-xs p-2 rounded-sm ${statusMessage.type === 'error' ? 'bg-destructive/10 text-destructive' : 'bg-green-500/10 text-green-500'}`}>
              {statusMessage.type === 'error' ? <AlertCircle className="w-3 h-3 flex-shrink-0" /> : <CheckCircle2 className="w-3 h-3 flex-shrink-0" />}
              <span className="break-words">{statusMessage.text}</span>
            </div>
          )}

          {confirmState === 'none' ? (
            <>
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider px-1">Switch Branch</span>
                <div className="max-h-32 overflow-y-auto flex flex-col gap-1">
                  {branches.map((b) => (
                    <button
                      key={b.name}
                      onClick={() => {
                        setCurrentBranch(b.name);
                        setIsOpen(false);
                      }}
                      className={`text-left px-2 py-1 text-sm rounded-sm hover:bg-secondary ${b.name === currentBranch ? 'bg-primary/10 text-primary font-medium' : 'text-foreground'}`}
                    >
                      {b.name}
                    </button>
                  ))}
                </div>
              </div>
              
              <hr className="border-border" />

              <div className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider px-1">Create from {currentBranch}</span>
                <div className="flex items-center gap-1">
                  <input 
                    type="text" 
                    placeholder="New branch name" 
                    value={newBranchName}
                    onChange={(e) => setNewBranchName(e.target.value)}
                    className="flex-1 min-w-0 bg-background text-sm border border-border rounded-sm px-2 py-1 outline-none focus:border-primary"
                  />
                  <button 
                    onClick={handleCreate}
                    className="bg-primary text-primary-foreground p-1 rounded-sm hover:opacity-90 disabled:opacity-50 flex-shrink-0"
                    disabled={!newBranchName}
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {currentBranch !== 'main' && (
                <>
                  <hr className="border-border" />
                  
                  <div className="flex flex-col gap-1">
                    <span className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wider px-1">Merge {currentBranch} into</span>
                    <div className="flex items-center gap-1">
                      <input 
                        type="text" 
                        placeholder="Target branch (e.g. main)" 
                        value={targetBranchName}
                        onChange={(e) => setTargetBranchName(e.target.value)}
                        className="flex-1 min-w-0 bg-background text-sm border border-border rounded-sm px-2 py-1 outline-none focus:border-primary"
                      />
                      <button 
                        onClick={() => setConfirmState('merge')}
                        className="bg-blue-600 text-white p-1 rounded-sm hover:opacity-90 disabled:opacity-50 flex-shrink-0"
                        disabled={!targetBranchName}
                      >
                        <GitMerge className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <hr className="border-border" />
                  
                  <button 
                    onClick={() => setConfirmState('delete')}
                    className="flex items-center gap-2 text-destructive hover:bg-destructive/10 text-sm px-2 py-1.5 rounded-sm transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>Delete Branch</span>
                  </button>
                </>
              )}
            </>
          ) : (
            <div className="flex flex-col gap-3 p-2">
              <span className="text-sm font-medium text-foreground">
                {confirmState === 'merge' 
                  ? `Merge '${currentBranch}' into '${targetBranchName}'?` 
                  : `Are you sure you want to delete '${currentBranch}'?`}
              </span>
              <div className="flex gap-2">
                <button 
                  onClick={() => confirmState === 'merge' ? executeMerge() : executeDelete()}
                  className="flex-1 bg-primary text-primary-foreground py-1.5 rounded-sm text-sm hover:opacity-90"
                >
                  Confirm
                </button>
                <button 
                  onClick={() => setConfirmState('none')}
                  className="flex-1 bg-secondary text-secondary-foreground py-1.5 rounded-sm text-sm hover:opacity-90"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
