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

interface AgentState {
  isConnected: boolean;
  activeNodeId: string | null;
  fileTree: FileNode[];
  logs: LogEntry[];
  currentDiff: { original: string; modified: string; filePath: string } | null;
  nodes: GraphNode[];
  edges: GraphEdge[];

  // Actions
  connectWebSocket: (repoId: string) => void;
  disconnectWebSocket: () => void;
  setActiveNode: (nodeId: string | null) => void;
  updateFileTree: (tree: FileNode[]) => void;
  addLog: (log: Omit<LogEntry, 'id' | 'timestamp'>) => void;
  setCurrentDiff: (diff: { original: string; modified: string; filePath: string } | null) => void;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
}

let ws: WebSocket | null = null;

export const useAgentStore = create<AgentState>((set, get) => ({
  isConnected: false,
  activeNodeId: null,
  fileTree: [
    {
      name: 'src', isDir: true, path: '/src', children: [
        { name: 'main.py', isDir: false, path: '/src/main.py', status: 'unmodified' },
        { name: 'utils.py', isDir: false, path: '/src/utils.py', status: 'modified' }
      ]
    },
    { name: 'tests', isDir: true, path: '/tests', children: [] },
    { name: 'README.md', isDir: false, path: '/README.md', status: 'unmodified' }
  ],
  logs: [],
  currentDiff: null,
  nodes: [],
  edges: [],

  connectWebSocket: (repoId: string) => {
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
  setGraph: (nodes, edges) => set({ nodes, edges })
}));
