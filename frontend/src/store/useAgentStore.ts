import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type AgentRole = 
  | 'ceo' 
  | 'product_manager' 
  | 'scrum_master' 
  | 'architect' 
  | 'backend_engineer' 
  | 'frontend_engineer' 
  | 'data_engineer' 
  | 'security_auditor' 
  | 'peer_review_reviewer' 
  | 'automation_tester' 
  | 'infrastructure_engineer' 
  | 'release_manager'
  | 'planner' // legacy
  | 'engineer' // legacy
  | 'reviewer' // legacy
  | 'tester'; // legacy

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

export interface TaskJourneyStep {
  agent: string;
  role: string;
  status: string;
  icon: any;
  description: string;
  output: string;
}

export interface ConflictFile {
  path: string;
  content: string;
}

export interface Task {
  id: string | number;
  title: string;
  owner: string;
  status: string;
  priority: string;
  journey?: TaskJourneyStep[];
  bandContext?: any;
}

interface DemoSnapshot {
  fileTree: FileNode[];
  logs: LogEntry[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  tasks: Task[];
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
  currentOrgSlug: string;
  repos: { id: string; name: string; fs_path: string }[];
  branches: { id: string; name: string; protected: boolean }[];
  currentBranch: string;
  tasks: Task[];
  activeTab: 'graph' | 'diff';

  activeFeatureScope: string | null;
  setActiveFeatureScope: (scope: string | null) => void;

  conflictFiles: ConflictFile[];
  conflictTargetBranch: string | null;
  setConflictFiles: (files: ConflictFile[]) => void;
  setConflictTargetBranch: (branch: string | null) => void;
  resolveMergeConflict: (resolvedFiles: ConflictFile[]) => Promise<void>;

  setActiveTab: (tab: 'graph' | 'diff') => void;
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  fetchRepos: () => Promise<void>;
  fetchBranches: (repoId: string) => Promise<void>;
  createBranch: (name: string, sourceBranch: string) => Promise<void>;
  deleteBranch: (name: string) => Promise<void>;
  mergeBranch: (sourceBranch: string, targetBranch: string) => Promise<void>;
  setCurrentBranch: (branch: string) => void;
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
  setOrgSlug: (slug: string) => void;

  demoMode: boolean;
  demoSnapshot: DemoSnapshot | null;
  startDemoSession: (snapshot: DemoSnapshot) => void;
  stopDemoSession: () => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

let ws: WebSocket | null = null;

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      isConnected: false,
      activeNodeId: null,
      apiKeys: {},
      theme: 'light',
      currentRepoId: null,
      currentOrgSlug: 'default',
      repos: [],
      branches: [],
      currentBranch: 'main',
      fileTree: [],
      logs: [],
      currentDiff: null,
      nodes: [],
      edges: [],
      tasks: [],
      activeTab: 'graph',
      demoMode: false,
      demoSnapshot: null,

      activeFeatureScope: null,
      setActiveFeatureScope: (scope) => set({ activeFeatureScope: scope }),

      conflictFiles: [],
      conflictTargetBranch: null,
      setConflictFiles: (files) => set({ conflictFiles: files }),
      setConflictTargetBranch: (branch) => set({ conflictTargetBranch: branch }),

      setActiveTab: (tab) => set({ activeTab: tab }),
      setTasks: (tasks) => set({ tasks }),
      addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),

      fetchRepos: async () => {
        const { currentOrgSlug, currentRepoId, connectWebSocket } = get();
        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos`);
          const data = await res.json();
          const repos = data.repositories || [];
          set({ repos });
          
          if (repos.length > 0) {
            const repoExists = repos.find((r: any) => r.fs_path === currentRepoId);
            if (!currentRepoId || !repoExists) {
              get().connectWebSocket(repos[0].fs_path);
              set({ activeTab: 'graph', currentDiff: null });
            } else {
              get().connectWebSocket(currentRepoId);
            }
          } else {
            set({ currentRepoId: '', isConnected: false, fileTree: [], activeTab: 'graph', currentDiff: null });
            if (ws) {
              ws.close();
              ws = null;
            }
          }
        } catch (e) {
          console.error("Failed to fetch repos", e);
        }
      },

      fetchBranches: async (repoId: string) => {
        const { currentOrgSlug, repos } = get();
        const repo = repos.find((r) => r.fs_path === repoId);
        const actualRepoId = repo ? repo.id : repoId;
        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches`);
          const data = await res.json();
          const branches = data.branches || [];
          set({ branches });
          
          const current = get().currentBranch;
          if (branches.length > 0 && !branches.find((b: any) => b.name === current)) {
             set({ currentBranch: branches[0].name });
          } else if (branches.length === 0) {
             set({ currentBranch: 'main' });
          }
        } catch (e) {
          console.error("Failed to fetch branches", e);
        }
      },

      createBranch: async (name: string, sourceBranch: string) => {
        const { currentOrgSlug, currentRepoId, repos } = get();
        if (!currentRepoId) return;
        const repo = repos.find((r) => r.fs_path === currentRepoId);
        const actualRepoId = repo ? repo.id : currentRepoId;
        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, source_branch: sourceBranch })
          });
          
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to create branch');
          }
          
          await get().fetchBranches(currentRepoId);
          set({ currentBranch: name });
          get().fetchFileTree(currentRepoId);
        } catch (e: any) {
          console.error("Failed to create branch", e);
          throw e;
        }
      },

      deleteBranch: async (name: string) => {
        const { currentOrgSlug, currentRepoId, currentBranch, repos } = get();
        if (!currentRepoId) return;
        const repo = repos.find((r) => r.fs_path === currentRepoId);
        const actualRepoId = repo ? repo.id : currentRepoId;
        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/${name}`, {
            method: 'DELETE'
          });
          
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to delete branch');
          }
          
          await get().fetchBranches(currentRepoId);
          if (currentBranch === name) {
            set({ currentBranch: 'main' });
            get().fetchFileTree(currentRepoId);
          }
        } catch (e: any) {
          console.error("Failed to delete branch", e);
          throw e;
        }
      },

      mergeBranch: async (sourceBranch: string, targetBranch: string) => {
        const { currentOrgSlug, currentRepoId, repos } = get();
        if (!currentOrgSlug || !currentRepoId) return;
        const repo = repos.find((r) => r.fs_path === currentRepoId);
        const actualRepoId = repo ? repo.id : currentRepoId;

        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/merge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_branch: sourceBranch, target_branch: targetBranch })
          });
          
          if (res.status === 409) {
            const errorData = await res.json();
            get().setConflictFiles(errorData.detail.conflict_files);
            get().setConflictTargetBranch(targetBranch);
            throw new Error("Merge conflict detected");
          }

          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || "Failed to merge branch");
          }
          
          get().fetchBranches(currentRepoId);
          get().fetchFileTree(currentRepoId);
        } catch (e: any) {
          console.error("Failed to merge branch", e);
          throw e;
        }
      },

      resolveMergeConflict: async (resolvedFiles: ConflictFile[]) => {
        const { currentOrgSlug, currentRepoId, currentBranch, conflictTargetBranch, repos } = get();
        if (!currentOrgSlug || !currentRepoId || !conflictTargetBranch) return;

        const repo = repos.find((r) => r.fs_path === currentRepoId);
        const actualRepoId = repo ? repo.id : currentRepoId;

        try {
          const res = await fetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/merge/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source_branch: currentBranch,
              target_branch: conflictTargetBranch,
              resolved_files: resolvedFiles
            })
          });

          if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.detail || "Failed to resolve merge");
          }

          get().setConflictFiles([]);
          get().setConflictTargetBranch(null);
          
          get().fetchBranches(currentRepoId);
          get().fetchFileTree(currentRepoId);
        } catch (e: any) {
          console.error("Failed to resolve conflict", e);
          throw e;
        }
      },

      setCurrentBranch: (branch: string) => {
        const { currentRepoId } = get();
        set({ currentBranch: branch, activeTab: 'graph', currentDiff: null });
        if (currentRepoId) {
          get().fetchFileTree(currentRepoId);
        }
      },

      fetchFileTree: async (repoId: string) => {
        const { currentBranch } = get();
        try {
          const res = await fetch(`${API_URL}/api/repos/${repoId}/files?branch=${currentBranch}`);
          const data = await res.json();
          set({ fileTree: data.files || [] });
        } catch (e) {
          console.error("Failed to fetch file tree", e);
        }
      },

      connectWebSocket: (repoId: string) => {
        const { currentOrgSlug } = get();
        set({ currentRepoId: repoId, isConnected: false });
        
        get().fetchBranches(repoId).then(() => {
          get().fetchFileTree(repoId);
        });

        if (ws) {
          ws.close();
        }

        ws = new WebSocket(`${WS_URL}/ws/${currentOrgSlug}/${repoId}`);

        ws.onopen = () => {
          set({ isConnected: true });
          get().addLog({ message: `WebSocket connected to control plane (org: ${currentOrgSlug})`, type: 'info' });
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
      setOrgSlug: (slug) => set({ currentOrgSlug: slug }),

      startDemoSession: (snapshot) => {
        set({
          demoMode: true,
          demoSnapshot: snapshot,
          fileTree: snapshot.fileTree,
          logs: snapshot.logs,
          nodes: snapshot.nodes,
          edges: snapshot.edges,
          tasks: snapshot.tasks,
        });
      },

      stopDemoSession: () => {
        const { demoSnapshot } = get();
        if (demoSnapshot) {
          set({
            demoMode: false,
            fileTree: [],
            logs: [],
            nodes: [],
            edges: [],
            tasks: [],
          });
        }
      }
    }),
    {
      name: 'agent-store',
      partialize: (state) => ({
        theme: state.theme,
        currentRepoId: state.currentRepoId,
        currentOrgSlug: state.currentOrgSlug,
        currentBranch: state.currentBranch,
        apiKeys: state.apiKeys,
        currentDiff: state.currentDiff,
        activeNodeId: state.activeNodeId,
        activeTab: state.activeTab,
      }),
    }
  )
);
