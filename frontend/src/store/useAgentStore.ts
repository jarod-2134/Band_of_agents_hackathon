import { create } from 'zustand';

export type AgentRole = 'planner' | 'engineer' | 'reviewer' | 'tester';

export interface LogEntry {
  id: string;
  timestamp: number;
  agentRole?: AgentRole;
  message: string;
  type: 'info' | 'error' | 'thought' | 'action';
}

export interface FileNode {
  name: string;
  isDir: boolean;
  children?: FileNode[];
  status?: 'modified' | 'reading' | 'unmodified';
  content?: string;
  path: string;
}

export interface GraphNode {
  id: string;
  data: { label: string };
  style?: any;
  role?: string;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  animated?: boolean;
  style?: any;
}

interface DemoSnapshot {
  fileTree: FileNode[];
  logs: LogEntry[];
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface AgentState {
  isConnected: boolean;
  activeNodeId: string | null;
  fileTree: FileNode[];
  logs: LogEntry[];
  currentDiff: { original: string; modified: string; filePath: string } | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  apiKeys: Record<string, string>;
  theme: string;
  currentRepoId: string | null;
  demoMode: boolean;
  demoSnapshot: DemoSnapshot | null;

  fetchFileTree: (repoId: string) => Promise<void>;
  connectWebSocket: (repoId: string) => void;
  disconnectWebSocket: () => void;
  sendMessage: (payload: any) => void;
  setActiveNode: (nodeId: string | null) => void;
  updateFileTree: (tree: FileNode[]) => void;
  addLog: (log: Omit<LogEntry, 'id' | 'timestamp'>) => void;
  setCurrentDiff: (diff: { original: string; modified: string; filePath: string } | null) => void;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  setApiKey: (provider: string, key: string) => void;
  setTheme: (theme: string) => void;
  startDemoSession: (payload: {
    fileTree: FileNode[];
    logs: LogEntry[];
    nodes: GraphNode[];
    edges: GraphEdge[];
  }) => void;
  stopDemoSession: () => void;
}

let ws: WebSocket | null = null;

export const useAgentStore = create<AgentState>((set, get) => ({
  isConnected: false,
  activeNodeId: null,
  apiKeys: {},
  theme: 'light',
  currentRepoId: null,
  fileTree: [],
  logs: [],
  currentDiff: null,
  nodes: [],
  edges: [],
  demoMode: false,
  demoSnapshot: null,

  fetchFileTree: async (repoId: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/repos/${repoId}/files`);
      const data = await res.json();
      set({ fileTree: data.files || [] });
    } catch (e) {
      console.error("Failed to fetch file tree", e);
    }
  },

  connectWebSocket: (repoId: string) => {
    set({ currentRepoId: repoId });
    get().fetchFileTree(repoId);

    if (ws) {
      ws.close();
    }

    ws = new WebSocket(`ws://localhost:8000/ws/${repoId}`);

    ws.onopen = () => {
      set({ isConnected: true });
      get().addLog({ message: "WebSocket connected to control plane", type: 'info' });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'log') {
          get().addLog({ message: data.payload, type: data.logType || 'info', agentRole: data.agentRole });
        } else if (data.type === 'active_node') {
          set({ activeNodeId: data.payload });
        } else if (data.type === 'graph_update') {
          set({ nodes: data.payload.nodes, edges: data.payload.edges });
        }
      } catch (e) {
        console.error("Failed to parse websocket message", e);
      }
    };

    ws.onclose = () => {
      set({ isConnected: false });
      get().addLog({ message: "WebSocket disconnected", type: 'error' });
    };
  },

  disconnectWebSocket: () => {
    if (ws) {
      ws.close();
      ws = null;
    }
  },

  sendMessage: (payload: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  },

  setActiveNode: (nodeId) => set({ activeNodeId: nodeId }),
  updateFileTree: (tree) => set({ fileTree: tree }),
  addLog: (log) => set((state) => ({
    logs: [...state.logs, {
      ...log,
      id: Math.random().toString(36).substring(7),
      timestamp: Date.now()
    }]
  })),
  setCurrentDiff: (diff) => set({ currentDiff: diff }),
  setGraph: (nodes, edges) => set({ nodes, edges }),
  setApiKey: (provider, key) => set((state) => ({ apiKeys: { ...state.apiKeys, [provider]: key } })),
  setTheme: (theme) => {
    set({ theme });
    const html = document.documentElement;
    html.classList.forEach(c => {
      if (c.startsWith('theme-')) html.classList.remove(c);
    });
    html.classList.remove('dark');
    html.classList.add(`theme-${theme}`);
  },

  startDemoSession: ({ fileTree, logs, nodes, edges }) => {
    const state = get();

    if (!state.demoMode) {
      set({
        demoMode: true,
        demoSnapshot: {
          fileTree: state.fileTree,
          logs: state.logs,
          nodes: state.nodes,
          edges: state.edges,
        },
        fileTree,
        logs,
        nodes,
        edges,
      });
    }
  },

  stopDemoSession: () => {
    const snapshot = get().demoSnapshot;

    if (snapshot) {
      set({
        demoMode: false,
        demoSnapshot: null,
        fileTree: snapshot.fileTree,
        logs: snapshot.logs,
        nodes: snapshot.nodes,
        edges: snapshot.edges,
      });
    } else {
      set({
        demoMode: false,
        demoSnapshot: null,
      });
    }
  },
}));