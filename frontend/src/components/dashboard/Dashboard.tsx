import { useState } from 'react';
import { useAgentStore, type FileNode } from '@/store/useAgentStore';
import { GraphViewer } from './GraphViewer';
import { DiffViewer } from './DiffViewer';
import { LogTerminal } from './LogTerminal';
import { Folder, File, Code, Bot } from 'lucide-react';

export function Dashboard() {
  const { fileTree, setCurrentDiff } = useAgentStore();
  const [activeTab, setActiveTab] = useState<'graph' | 'diff'>('graph');

  const renderTree = (nodes: FileNode[], depth = 0) => {
    return nodes.map((node) => (
      <div key={node.path} style={{ paddingLeft: `${depth * 12}px` }}>
        <div 
          className={`flex items-center gap-2 py-1 px-2 hover:bg-secondary cursor-pointer text-sm ${node.status === 'modified' ? 'text-blue-600 font-semibold' : ''}`}
          onClick={async () => {
            if (!node.isDir) {
              setActiveTab('diff');
              const { currentRepoId } = useAgentStore.getState();
              if (currentRepoId) {
                try {
                  const res = await fetch(`http://localhost:8000/api/repos/${currentRepoId}/file/${encodeURIComponent(node.path)}`);
                  if (res.ok) {
                    const data = await res.json();
                    setCurrentDiff({
                      filePath: node.path,
                      original: data.content,
                      modified: data.content // We'll update this when agents actually modify it
                    });
                  }
                } catch (e) {
                  console.error("Failed to fetch file content", e);
                }
              }
            }
          }}
        >
          {node.isDir ? <Folder className="w-4 h-4 text-muted-foreground" /> : <File className="w-4 h-4 text-muted-foreground" />}
          {node.name}
        </div>
        {node.children && renderTree(node.children, depth + 1)}
      </div>
    ));
  };

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Sidebar - File Tree */}
      <div className="w-64 border-r border-border bg-white flex flex-col">
        <div className="px-4 py-2 border-b border-border font-bold text-xs tracking-widest text-muted-foreground">
          WORKSPACE
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {renderTree(fileTree)}
        </div>
      </div>

      {/* Center Canvas */}
      <div className="flex-1 flex flex-col p-4 gap-4 bg-secondary/30">
        
        <div className="flex gap-2">
          <button 
            onClick={() => setActiveTab('graph')}
            className={`px-4 py-1.5 text-sm font-semibold rounded-md border flex items-center gap-2 ${activeTab === 'graph' ? 'bg-black text-white border-black' : 'bg-white border-border hover:bg-secondary'}`}
          >
            <Bot className="w-4 h-4" /> Agents
          </button>
          <button 
            onClick={() => setActiveTab('diff')}
            className={`px-4 py-1.5 text-sm font-semibold rounded-md border flex items-center gap-2 ${activeTab === 'diff' ? 'bg-black text-white border-black' : 'bg-white border-border hover:bg-secondary'}`}
          >
            <Code className="w-4 h-4" /> Diff View
          </button>
        </div>

        <div className="flex-1 min-h-0">
          {activeTab === 'graph' ? <GraphViewer /> : <DiffViewer />}
        </div>

        <div className="h-1/3 min-h-[200px]">
          <LogTerminal />
        </div>
        
      </div>
    </div>
  );
}
