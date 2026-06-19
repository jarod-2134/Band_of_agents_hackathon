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
  activeTab: 'graph' | 'diff' | 'chats';

  activeChatroomId: string | null;
  activeChatMessages: any[];
  isFetchingMessages: boolean;
  setActiveChatroomId: (roomId: string | null) => void;
  fetchChatMessages: (roomId: string) => Promise<void>;
  chats: any[];
  fetchChats: () => Promise<void>;

  activeFeatureScope: string | null;
  setActiveFeatureScope: (scope: string | null) => void;

  conflictFiles: ConflictFile[];
  conflictTargetBranch: string | null;
  setConflictFiles: (files: ConflictFile[]) => void;
  setConflictTargetBranch: (branch: string | null) => void;
  resolveMergeConflict: (resolvedFiles: ConflictFile[]) => Promise<void>;

  setActiveTab: (tab: 'graph' | 'diff' | 'chats') => void;
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
  sendMessage: (payload: any) => boolean;
  setActiveNode: (nodeId: string | null) => void;
  updateFileTree: (tree: FileNode[]) => void;
  addLog: (log: Omit<LogEntry, 'id' | 'timestamp'>) => void;
  setCurrentDiff: (diff: { original: string; modified: string; filePath: string } | null) => void;
  setGraph: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  setApiKey: (provider: string, key: string) => void;
  setTheme: (theme: string) => void;
  setOrgSlug: (slug: string) => void;
  token: string | null;
  setToken: (token: string | null) => void;

  demoMode: boolean;
  demoSnapshot: DemoSnapshot | null;
  startDemoSession: (snapshot: DemoSnapshot) => void;
  stopDemoSession: () => void;
}

// If VITE_API_URL is set, use it. Otherwise use relative URLs that go through the Vite proxy.
// This makes the app work via localhost, ngrok, or any other tunnel without changing .env.
export const API_URL = import.meta.env.VITE_API_URL || '';
// WebSockets must connect directly to the backend (cannot be proxied through Vite dev server).
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

let ws: WebSocket | null = null;
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null;
let wsIntentionalClose = false;

/**
 * Authenticated fetch wrapper for the control-plane API.
 *
 * The backend's LifecycleSecurityMiddleware requires a Bearer JWT on every
 * non-exempt path. This attaches the stored token to all dashboard API calls,
 * merges JSON content headers, and bounces to /login on a 401 so stale tokens
 * don't silently break the UI.
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = useAgentStore.getState().token;
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string> | undefined),
  };

  // Default to JSON when the caller provides a body and didn't set a content type
  if (init.body && !headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(input, { ...init, headers });

  if (res.status === 401) {
    useAgentStore.getState().setToken(null);
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.assign('/login');
    }
  }
  return res;
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
      token: null,
      setToken: (token) => set({ token }),
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
      activeChatroomId: null,
      activeChatMessages: [],
      isFetchingMessages: false,
      setActiveChatroomId: (roomId) => set({ activeChatroomId: roomId }),
      fetchChatMessages: async (roomId) => {
        const { currentOrgSlug } = get();
        set({ isFetchingMessages: true });
        try {
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/chats/${roomId}/messages`);
          const data = await res.json();
          set({ activeChatMessages: data.messages || [], isFetchingMessages: false });
        } catch (e) {
          console.error("Failed to fetch chat messages", e);
          set({ isFetchingMessages: false });
        }
      },
      chats: [],
      fetchChats: async () => {
        const { currentOrgSlug } = get();
        try {
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/chats`);
          const data = await res.json();
          set({ chats: data.chats || [] });
        } catch (e) {
          console.error("Failed to fetch chats", e);
        }
      },
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
        const maxRetries = 6;
        const retryDelayMs = 3000;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
          try {
            const { currentOrgSlug, currentRepoId } = get();
            const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos`);
            if (!res.ok) {
              throw new Error(`HTTP ${res.status}`);
            }
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
            return; // success — stop retrying
          } catch (e) {
            if (attempt < maxRetries) {
              console.warn(`fetchRepos failed (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${retryDelayMs / 1000}s...`, e);
              await new Promise(resolve => setTimeout(resolve, retryDelayMs));
            } else {
              console.error("fetchRepos failed after all retries:", e);
            }
          }
        }
      },


      fetchBranches: async (repoId: string) => {
        const { currentOrgSlug, repos } = get();
        const repo = repos.find((r) => r.fs_path === repoId);
        const actualRepoId = repo ? repo.id : repoId;
        try {
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches`);
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
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches`, {
            method: 'POST',
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
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/${name}`, {
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
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/merge`, {
            method: 'POST',
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
          const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/repos/${actualRepoId}/branches/merge/resolve`, {
            method: 'POST',
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
          const res = await apiFetch(`${API_URL}/api/repos/${repoId}/files?branch=${currentBranch}`);
          const data = await res.json();
          set({ fileTree: data.files || [] });
        } catch (e) {
          console.error("Failed to fetch file tree", e);
        }
      },

      connectWebSocket: (repoId: string) => {
        const { currentOrgSlug, currentRepoId } = get();
        const isSameRepo = currentRepoId === repoId;
        set({ currentRepoId: repoId, isConnected: false });

        // Only re-fetch branches and file tree when switching to a different repo.
        // Skip on reconnects to the same repo to prevent the polling loop from
        // hammering the backend with GET /branches and GET /files every 3 seconds.
        if (!isSameRepo) {
          get().fetchBranches(repoId).then(() => {
            get().fetchFileTree(repoId);
          });
        }

        // Cancel any pending reconnect and start a fresh connection
        if (wsReconnectTimer) {
          clearTimeout(wsReconnectTimer);
          wsReconnectTimer = null;
        }
        if (ws) {
          wsIntentionalClose = true;
          ws.close();
        }

        wsIntentionalClose = false;
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
          // Only attempt auto-reconnect if this wasn't an intentional close
          // (e.g. logout, repo switch). This lets the UI survive a backend
          // restart/boot delay without the user having to refresh the page.
          if (!wsIntentionalClose) {
            get().addLog({ message: "Control plane disconnected — retrying in 3s...", type: 'error' });
            if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
            wsReconnectTimer = setTimeout(() => {
              const rid = get().currentRepoId;
              if (rid) get().connectWebSocket(rid);
            }, 3000);
          }
        };
      },

      disconnectWebSocket: () => {
        wsIntentionalClose = true;
        if (wsReconnectTimer) {
          clearTimeout(wsReconnectTimer);
          wsReconnectTimer = null;
        }
        if (ws) {
          ws.close();
          ws = null;
        }
      },

      sendMessage: (payload: any) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(payload));
          return true;
        }
        return false;
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
        activeChatroomId: state.activeChatroomId,
        token: state.token,
      }),
    }
  )
);
