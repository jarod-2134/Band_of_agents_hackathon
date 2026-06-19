import { useState, useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { FileWarning, Check, X, ArrowDown } from 'lucide-react';
import { DiffEditor } from '@monaco-editor/react';

// Simple parser to extract the "ours" and "theirs" versions from conflict markers
const parseConflict = (content: string) => {
  let ours = '';
  let theirs = '';
  let state = 'normal';
  const lines = content.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('<<<<<<<')) {
      state = 'ours';
      continue;
    }
    if (line.startsWith('=======')) {
      state = 'theirs';
      continue;
    }
    if (line.startsWith('>>>>>>>')) {
      state = 'normal';
      continue;
    }
    
    if (state === 'normal') {
      ours += line + '\n';
      theirs += line + '\n';
    } else if (state === 'ours') {
      ours += line + '\n';
    } else if (state === 'theirs') {
      theirs += line + '\n';
    }
  }
  
  return {
    ours: ours.endsWith('\n') ? ours.slice(0, -1) : ours,
    theirs: theirs.endsWith('\n') ? theirs.slice(0, -1) : theirs
  };
};

export function ConflictResolver() {
  const conflictFiles = useAgentStore(state => state.conflictFiles);
  const conflictTargetBranch = useAgentStore(state => state.conflictTargetBranch);
  const currentBranch = useAgentStore(state => state.currentBranch);
  const resolveMergeConflict = useAgentStore(state => state.resolveMergeConflict);
  const setConflictFiles = useAgentStore(state => state.setConflictFiles);
  const setConflictTargetBranch = useAgentStore(state => state.setConflictTargetBranch);

  const [resolvedContent, setResolvedContent] = useState<Record<string, string>>({});
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [markedResolved, setMarkedResolved] = useState<Set<string>>(new Set());
  const [errorStatus, setErrorStatus] = useState<string | null>(null);

  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);

  useEffect(() => {
    if (conflictFiles.length > 0) {
      if (!activeFilePath) setActiveFilePath(conflictFiles[0].path);
      
      const initialContent: Record<string, string> = {};
      conflictFiles.forEach(f => {
        if (resolvedContent[f.path] === undefined) {
          initialContent[f.path] = parseConflict(f.content).theirs;
        }
      });
      setResolvedContent(prev => ({...prev, ...initialContent}));
    }
  }, [conflictFiles]);

  const activeFile = conflictFiles.find(f => f.path === activeFilePath);
  const currentContent = activeFilePath ? resolvedContent[activeFilePath] || '' : '';

  const updateDecorations = () => {
    if (!editorRef.current || !monacoRef.current) return;
    const model = editorRef.current.getModel();
    if (!model) return;

    const matches = model.findMatches('<<<<<<<[\\s\\S]*?=======[\\s\\S]*?>>>>>>>.*', false, true, false, null, true);
    
    const newDecorations = matches.map((match: any) => ({
      range: match.range,
      options: {
        isWholeLine: true,
        className: 'bg-destructive/20 border-l-4 border-destructive',
        overviewRuler: {
          color: 'rgba(239, 68, 68, 0.8)',
          position: monacoRef.current.editor.OverviewRulerLane.Right
        }
      }
    }));

    decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, newDecorations);
  };

  useEffect(() => {
    updateDecorations();
  }, [currentContent]);

  if (!conflictFiles || conflictFiles.length === 0) return null;

  const handleContentChange = (value: string) => {
    if (activeFilePath) {
      setResolvedContent(prev => ({
        ...prev,
        [activeFilePath]: value
      }));
      // If user edits, unmark as resolved automatically so they don't accidentally submit unresolved stuff
      if (markedResolved.has(activeFilePath)) {
        const newResolved = new Set(markedResolved);
        newResolved.delete(activeFilePath);
        setMarkedResolved(newResolved);
      }
    }
  };

  const jumpToNextConflict = () => {
    if (!editorRef.current || !monacoRef.current) return;
    const model = editorRef.current.getModel();
    if (!model) return;

    const position = editorRef.current.getPosition();
    const matches = model.findMatches('<<<<<<<', false, false, false, null, false);
    
    if (matches.length > 0) {
      // Find the first match that is after the current cursor
      let nextMatch = matches.find((m: any) => m.range.startLineNumber > position.lineNumber);
      if (!nextMatch) nextMatch = matches[0]; // Wrap around
      
      editorRef.current.revealLineInCenter(nextMatch.range.startLineNumber);
      editorRef.current.setPosition({ lineNumber: nextMatch.range.startLineNumber, column: 1 });
      editorRef.current.focus();
    }
  };

  const toggleResolved = (path: string) => {
    const newResolved = new Set(markedResolved);
    if (newResolved.has(path)) {
      newResolved.delete(path);
    } else {
      newResolved.add(path);
    }
    setMarkedResolved(newResolved);
  };

  const cancelMerge = () => {
    setConflictFiles([]);
    setConflictTargetBranch(null);
  };

  const completeMerge = async () => {
    try {
      setErrorStatus(null);
      // Construct the resolved files payload
      const payload = conflictFiles.map(f => ({
        path: f.path,
        content: resolvedContent[f.path]
      }));
      await resolveMergeConflict(payload);
    } catch (err: any) {
      setErrorStatus(err.message || 'Failed to complete merge');
    }
  };

  const allResolved = conflictFiles.length > 0 && conflictFiles.every(f => markedResolved.has(f.path));

  return (
    <div className="w-full h-full flex flex-col bg-card overflow-hidden">
      <div className="w-full h-full flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-secondary/30">
          <div>
            <h2 className="text-xl font-bold flex items-center gap-2">
              <FileWarning className="w-6 h-6 text-destructive" />
              Resolve Merge Conflicts
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Merging <span className="font-semibold text-foreground">{currentBranch}</span> into <span className="font-semibold text-foreground">{conflictTargetBranch}</span> requires manual resolution.
            </p>
            {errorStatus && (
              <p className="text-sm font-semibold text-destructive mt-2">
                {errorStatus}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={cancelMerge}
              className="px-4 py-2 border border-border rounded-md hover:bg-secondary transition-colors text-sm font-medium"
            >
              Cancel Merge
            </button>
            <button 
              onClick={completeMerge}
              disabled={!allResolved}
              className={`px-4 py-2 rounded-md transition-colors text-sm font-medium flex items-center gap-2
                ${allResolved ? 'bg-primary text-primary-foreground hover:opacity-90' : 'bg-muted text-muted-foreground cursor-not-allowed'}
              `}
            >
              <Check className="w-4 h-4" />
              Complete Merge
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar */}
          <div className="w-64 border-r border-border bg-secondary/10 flex flex-col">
            <div className="p-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b border-border">
              Conflicted Files ({conflictFiles.length})
            </div>
            <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
              {conflictFiles.map(file => {
                const isResolved = markedResolved.has(file.path);
                const isActive = activeFilePath === file.path;
                return (
                  <button
                    key={file.path}
                    onClick={() => setActiveFilePath(file.path)}
                    className={`flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors text-left
                      ${isActive ? 'bg-primary/10 border-primary/30 border' : 'border border-transparent hover:bg-secondary'}
                    `}
                  >
                    <span className="truncate pr-2 font-medium" title={file.path}>
                      {file.path.split('/').pop()}
                    </span>
                    {isResolved ? (
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                    ) : (
                      <X className="w-4 h-4 text-destructive flex-shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Editor Area */}
          <div className="flex-1 flex flex-col bg-background relative">
            {activeFile ? (
              <>
                <div className="p-3 border-b border-border flex items-center justify-between bg-secondary/20">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground font-mono">
                    {activeFile.path}
                  </div>
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={jumpToNextConflict}
                      className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border rounded-md"
                    >
                      <ArrowDown className="w-3.5 h-3.5" />
                      Next Conflict
                    </button>
                    <button
                      onClick={() => toggleResolved(activeFile.path)}
                      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 border rounded-md transition-colors
                        ${markedResolved.has(activeFile.path) 
                          ? 'bg-green-500/10 text-green-600 border-green-500/30 hover:bg-green-500/20' 
                          : 'bg-primary text-primary-foreground hover:opacity-90'}
                      `}
                    >
                      <Check className="w-3.5 h-3.5" />
                      {markedResolved.has(activeFile.path) ? 'Marked as Resolved' : 'Mark as Resolved'}
                    </button>
                  </div>
                </div>
                
                <div className="flex-1 p-4 relative">
                  <DiffEditor
                    height="100%"
                    theme="vs-dark"
                    original={activeFile ? parseConflict(activeFile.content).ours : ''}
                    modified={currentContent}
                    options={{
                      minimap: { enabled: false },
                      fontSize: 13,
                      wordWrap: 'on',
                      scrollBeyondLastLine: false,
                      renderSideBySide: true,
                      readOnly: false,
                      originalEditable: true,
                      ignoreTrimWhitespace: false
                    }}
                    onMount={(editor, monaco) => {
                      const modifiedEditor = editor.getModifiedEditor();
                      editorRef.current = modifiedEditor;
                      monacoRef.current = monaco;
                      
                      modifiedEditor.onDidChangeModelContent(() => {
                        handleContentChange(modifiedEditor.getValue());
                      });
                      
                      updateDecorations();
                    }}
                  />
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                Select a file to resolve conflicts
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
