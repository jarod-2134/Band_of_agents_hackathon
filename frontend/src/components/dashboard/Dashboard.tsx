import { useState } from 'react';
import { useAgentStore, type FileNode, API_URL, apiFetch } from '@/store/useAgentStore';
import { GraphViewer } from './GraphViewer';
import { DiffViewer } from './DiffViewer';
import { LogTerminal } from './LogTerminal';
import { Folder, File, Code, Bot, ChevronDown, ChevronRight, Clock3, Database, MessageSquare } from 'lucide-react';
import { ChatroomsViewer } from './ChatroomsViewer';

const mockDiffs: Record<string, { original: string; modified: string }> = {
  'frontend/src/Login.tsx': {
    original: `export function Login() {
  return (
    <form>
      <input type="email" />
      <input type="password" />
      <button>Sign In</button>
    </form>
  );
}`,
    modified: `import { useState } from 'react';

export function Login() {
  const [loading, setLoading] = useState(false);

  return (
    <form>
      <input type="email" required />
      <input type="password" required minLength={8} />
      <button disabled={loading}>
        {loading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
}`,
  },
  'frontend/src/auth.ts': {
    original: `export async function login(email: string, password: string) {
  return fetch('/api/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}`,
    modified: `export async function login(email: string, password: string) {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    throw new Error('Invalid email or password');
  }

  return response.json();
}`,
  },
  'frontend/src/components/dashboard/Dashboard.tsx': {
    original: `export function Dashboard() {
  return (
    <div>
      <GraphViewer />
      <LogTerminal />
    </div>
  );
}`,
    modified: `export function Dashboard() {
  const [terminalOpen, setTerminalOpen] = useState(true);

  return (
    <div>
      <GraphViewer />
      <LogTerminal
        isOpen={terminalOpen}
        onToggle={() => setTerminalOpen(!terminalOpen)}
      />
    </div>
  );
}`,
  },
  'frontend/src/components/dashboard/GraphViewer.tsx': {
    original: `const journey = [
  { agent: 'PM Agent', status: 'Completed' },
  { agent: 'Developer Agent', status: 'Working' },
];`,
    modified: `const tasks = [
  {
    id: 1,
    title: 'Build login page',
    journey: [
      { agent: 'PM Agent', status: 'Completed' },
      { agent: 'Developer Agent', status: 'Working' },
    ],
    bandContext: {
      type: 'implementation_task',
      from: 'PM Agent',
      to: 'Developer Agent',
    },
  },
];`,
  },
  'backend/agents/corporate.py': {
    original: `class DeveloperAgent:
    def run(self, task):
        return "done"`,
    modified: `class DeveloperAgent:
    def run(self, task):
        plan = self.read_task_context(task)
        changes = self.implement(plan)
        return self.create_handoff(changes)`,
  },
  'backend/main.py': {
    original: `app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok"}`,
    modified: `app = FastAPI()

@app.get("/")
def root():
    return {"status": "Band AI Control Plane running"}

@app.websocket("/ws/{repo_id}")
async def websocket_endpoint(websocket: WebSocket, repo_id: str):
    await websocket.accept()`,
  },
  'README.md': {
    original: `# Band AI

Multi-agent coding system.`,
    modified: `# Band AI Control Plane

A multi-agent software delivery workspace where PM, Developer, Reviewer, and QA agents coordinate through Band handoffs.`,
  },
};

export function Dashboard() {
  const fileTree = useAgentStore((state) => state.fileTree);
  const currentRepoId = useAgentStore((state) => state.currentRepoId);
  const activeTab = useAgentStore((state) => state.activeTab);
  const setActiveTab = useAgentStore((state) => state.setActiveTab);
  const currentDiff = useAgentStore((state) => state.currentDiff);
  const setCurrentDiff = useAgentStore((state) => state.setCurrentDiff);
  const currentBranch = useAgentStore((state) => state.currentBranch);
  const [terminalOpen, setTerminalOpen] = useState(false);
  // Tracks which directory paths are collapsed. A path in the set is collapsed;
  // absent means expanded. Top-level folders default to collapsed for a tidy tree.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggleFolder = (path: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const diffToDisplay = currentDiff || {
    filePath: 'frontend/src/Login.tsx',
    original: mockDiffs['frontend/src/Login.tsx'].original,
    modified: mockDiffs['frontend/src/Login.tsx'].modified,
  };

  const renderTree = (nodes: FileNode[], depth = 0) => {
    return nodes?.map((node) => {
      const isCollapsed = collapsed.has(node.path);
      return (
        <div key={node.path} style={{ paddingLeft: `${depth * 12}px` }}>
          <div
            className={`flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-secondary cursor-pointer text-sm ${
              node.status === 'modified' ? 'text-blue-600 font-semibold' : 'text-foreground'
            }`}
            onClick={() => {
              if (node.isDir) {
                toggleFolder(node.path);
                return;
              }
              setActiveTab('diff');

              setCurrentDiff({
                filePath: node.path,
                original: `// Loading original version...`,
                modified: `// Loading ${node.name}...`,
              });

              apiFetch(`${API_URL}/api/repos/${currentRepoId}/file/${encodeURIComponent(node.path)}?branch=${currentBranch}`)
                .then((res) => {
                  if (!res.ok) throw new Error('Network response was not ok');
                  return res.json();
                })
                .then((data) => {
                  setCurrentDiff({
                    filePath: node.path,
                    original: data.content ?? '',
                    modified: data.content ?? `// No agent modifications have been recorded for this file yet.`,
                  });
                })
                .catch((err) => {
                  setCurrentDiff({
                    filePath: node.path,
                    original: `// No previous version available for ${node.name}`,
                    modified: `// Failed to load file: ${err.message}`,
                  });
                });
            }}
          >
            {node.isDir ? (
              <>
                {isCollapsed
                  ? <ChevronRight className="w-3 h-3 text-muted-foreground" />
                  : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
                <Folder className="w-4 h-4 text-muted-foreground" />
              </>
            ) : (
              <>
                <ChevronRight className="w-3 h-3 text-transparent" />
                <File className="w-4 h-4 text-muted-foreground" />
              </>
            )}

            <span className="truncate">{node.name}</span>

            {node.status === 'modified' && (
              <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600">
                modified
              </span>
            )}
          </div>

          {node.isDir && !isCollapsed && node.children && renderTree(node.children, depth + 1)}
        </div>
      );
    });
  };

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="w-64 border-r border-border bg-card flex flex-col">
        <div className="px-4 py-2 border-b border-border font-bold text-xs tracking-widest text-muted-foreground">
          WORKSPACE
        </div>

        <div className="px-4 py-3 border-b border-border">
          <div className="text-sm font-semibold text-foreground">Project Files</div>
          <div className="text-xs text-muted-foreground mt-1">Files modified by agents</div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {fileTree.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground px-4">
              <Clock3 className="w-8 h-8 mb-3 opacity-70" />
              <div className="font-medium text-foreground">No repository loaded</div>
              <p className="text-xs mt-2">
                Run the demo workflow to populate files modified by agents.
              </p>
            </div>
          ) : (
            renderTree(fileTree)
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col p-4 gap-4 bg-background">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('graph')}
            className={`px-4 py-1.5 text-sm font-semibold rounded-md border flex items-center gap-2 transition-colors ${
              activeTab === 'graph'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-foreground border-border hover:bg-secondary'
            }`}
          >
            <Bot className="w-4 h-4" /> Agents
          </button>

          <button
            onClick={() => setActiveTab('diff')}
            className={`px-4 py-1.5 text-sm font-semibold rounded-md border flex items-center gap-2 transition-colors ${
              activeTab === 'diff'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-foreground border-border hover:bg-secondary'
            }`}
          >
            <Code className="w-4 h-4" /> Diff View
          </button>

          <button
            onClick={() => setActiveTab('chats')}
            className={`px-4 py-1.5 text-sm font-semibold rounded-md border flex items-center gap-2 transition-colors ${
              activeTab === 'chats'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-foreground border-border hover:bg-secondary'
            }`}
          >
            <MessageSquare className="w-4 h-4" /> Band Chatrooms
          </button>
        </div>

        <div className="flex-1 min-h-0">
          {!currentRepoId ? (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground bg-card rounded-md border border-border">
              <Database className="w-12 h-12 mb-4 opacity-20" />
              <h3 className="text-lg font-semibold text-foreground">No Repository Selected</h3>
              <p className="max-w-sm mt-2 text-sm">
                Please create or select a repository from the top left dropdown to start working.
              </p>
            </div>
          ) : activeTab === 'graph' ? (
            <GraphViewer />
          ) : activeTab === 'chats' ? (
            <ChatroomsViewer />
          ) : (
            <DiffViewer diff={diffToDisplay} />
          )}
        </div>

        <div className={terminalOpen ? 'h-56 shrink-0' : 'h-11 shrink-0'}>
          <LogTerminal isOpen={terminalOpen} onToggle={() => setTerminalOpen(!terminalOpen)} />
        </div>
      </div>
    </div>
  );
}