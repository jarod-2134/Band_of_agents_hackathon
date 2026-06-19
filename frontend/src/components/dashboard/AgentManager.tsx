import { useState, useEffect } from 'react';
import { useAgentStore, API_URL, apiFetch } from '@/store/useAgentStore';
import { Bot, Play, Square, Plus, Trash2, Send } from 'lucide-react';

export function AgentManager() {
  const currentOrgSlug = useAgentStore((state) => state.currentOrgSlug) || 'default';
  const apiKeys = useAgentStore((state) => state.apiKeys);
  const [agents, setAgents] = useState<any[]>([]);
  const [newName, setNewName] = useState('');
  const [newModel, setNewModel] = useState('gemini-2.5-flash');
  const [statusMessage, setStatusMessage] = useState<{text: string, type: 'error'|'success'} | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  // Inline task-assignment prompt state
  const [assignTargetId, setAssignTargetId] = useState<number | null>(null);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDesc, setTaskDesc] = useState('');

  const showStatus = (text: string, type: 'error'|'success') => {
    setStatusMessage({text, type});
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const fetchAgents = () => {
    apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents`)
      .then(r => r.json())
      .then(data => {
        if (data.agents) setAgents(data.agents);
      })
      .catch(err => console.error("Failed to fetch agents", err));
  };

  useEffect(() => {
    fetchAgents();
  }, [currentOrgSlug]);

  const handleCreateAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents`, {
        method: 'POST',
        body: JSON.stringify({ name: newName, model_spec: newModel })
      });
      if (res.ok) {
        setNewName('');
        fetchAgents();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleStart = async (id: number) => {
    const bandAgentId = apiKeys['band_agent_id'] || 'dummy';
    const bandAgentApiKey = apiKeys['bandai'] || 'dummy';
    try {
      await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/${id}/start?band_agent_id=${encodeURIComponent(bandAgentId)}&band_agent_api_key=${encodeURIComponent(bandAgentApiKey)}`, {
        method: 'POST'
      });
      fetchAgents();
    } catch (err) {
      console.error(err);
    }
  };

  const handleStop = async (id: number) => {
    try {
      await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/${id}/stop`, {
        method: 'POST'
      });
      fetchAgents();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      return;
    }
    try {
      await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/${id}`, {
        method: 'DELETE'
      });
      setConfirmDeleteId(null);
      showStatus('Agent deleted', 'success');
      fetchAgents();
    } catch (err) {
      console.error(err);
      setConfirmDeleteId(null);
      showStatus('Failed to delete agent', 'error');
    }
  };

  const openAssignPrompt = (id: number) => {
    setAssignTargetId(id);
    setTaskTitle('');
    setTaskDesc('');
  };

  const closeAssignPrompt = () => {
    setAssignTargetId(null);
    setTaskTitle('');
    setTaskDesc('');
  };

  const handleAssignTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (assignTargetId === null) return;
    try {
      const res = await apiFetch(`${API_URL}/orgs/${currentOrgSlug}/agents/${assignTargetId}/assign`, {
        method: 'POST',
        body: JSON.stringify({ title: taskTitle, description: taskDesc })
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        const note = data.dispatched_to_live_agent === false
          ? 'Task created (start the agent to dispatch it).'
          : 'Task assigned successfully!';
        showStatus(note, 'success');
        fetchAgents();
        closeAssignPrompt();
      } else {
        const err = await res.json().catch(() => ({}));
        showStatus(`Failed: ${err.detail || 'Unknown error'}`, 'error');
      }
    } catch (err) {
      console.error(err);
      showStatus('Failed to assign task', 'error');
    }
  };

  return (
    <div className="w-full h-full bg-background flex flex-col overflow-hidden">
      <div className="p-4 border-b border-border bg-card shrink-0">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Bot className="w-6 h-6 text-primary" />
          Agent Fleet Manager
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your autonomous agents, start/stop them, and assign tasks.
        </p>
      </div>

      {statusMessage && (
        <div className={`px-4 py-2 text-sm border-b font-medium flex items-center justify-center ${statusMessage.type === 'error' ? 'bg-destructive/10 text-destructive border-destructive/20' : 'bg-green-500/10 text-green-500 border-green-500/20'}`}>
          {statusMessage.text}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6">
        {/* Create Form */}
        <form onSubmit={handleCreateAgent} className="bg-card border border-border p-4 rounded-lg flex items-end gap-4 shadow-sm">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Agent Role/Name</label>
            <input 
              type="text" 
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="e.g. Frontend Engineer"
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            />
          </div>
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Model Spec</label>
            <select
              value={newModel}
              onChange={e => setNewModel(e.target.value)}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            >
              <option value="gemini-2.5-flash">Gemini 2.5 Flash (default)</option>
              <option value="gpt-4o">GPT-4o</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
            </select>
          </div>
          <button type="submit" className="bg-primary text-primary-foreground px-4 py-2 rounded-md font-medium text-sm flex items-center gap-2 hover:bg-primary/90 transition-colors">
            <Plus className="w-4 h-4" />
            Create Agent
          </button>
        </form>

        {/* Agent List */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map(agent => (
            <div key={agent.id} className="bg-card border border-border rounded-lg p-4 flex flex-col shadow-sm relative group">
              <button 
                onClick={() => handleDelete(agent.id)}
                className={`absolute top-4 right-4 transition-opacity ${confirmDeleteId === agent.id ? 'text-destructive opacity-100' : 'text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100'}`}
                title={confirmDeleteId === agent.id ? "Click again to confirm" : "Delete Agent"}
              >
                <Trash2 className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">{agent.name}</h3>
                  <div className="text-xs text-muted-foreground">{agent.model_spec}</div>
                </div>
              </div>

              <div className="mt-2 mb-4 flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${agent.operational_status === 'stopped' ? 'bg-red-500' : 'bg-green-500'}`}></span>
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  {agent.operational_status}
                </span>
              </div>

              <div className="flex items-center gap-2 mt-auto pt-4 border-t border-border">
                {agent.operational_status === 'stopped' ? (
                  <button 
                    onClick={() => handleStart(agent.id)}
                    className="flex-1 flex items-center justify-center gap-2 py-1.5 bg-green-500/10 text-green-500 hover:bg-green-500/20 text-xs font-semibold rounded-md transition-colors"
                  >
                    <Play className="w-3.5 h-3.5" /> Start
                  </button>
                ) : (
                  <button 
                    onClick={() => handleStop(agent.id)}
                    className="flex-1 flex items-center justify-center gap-2 py-1.5 bg-red-500/10 text-red-500 hover:bg-red-500/20 text-xs font-semibold rounded-md transition-colors"
                  >
                    <Square className="w-3.5 h-3.5" /> Stop
                  </button>
                )}
                <button
                  onClick={() => openAssignPrompt(agent.id)}
                  className="flex-1 flex items-center justify-center gap-2 py-1.5 bg-primary/10 text-primary hover:bg-primary/20 text-xs font-semibold rounded-md transition-colors"
                >
                  <Send className="w-3.5 h-3.5" /> Task
                </button>
              </div>
            </div>
          ))}
          {agents.length === 0 && (
            <div className="col-span-full py-12 text-center text-muted-foreground border-2 border-dashed border-border rounded-lg">
              No agents provisioned yet. Create one above!
            </div>
          )}
        </div>
      </div>

      {/* Inline task-assignment prompt */}
      {assignTargetId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={closeAssignPrompt}
        >
          <div
            className="w-full max-w-md bg-card border border-border rounded-lg shadow-xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-foreground mb-1">Assign Task</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Describe what agent #{assignTargetId} should work on.
            </p>
            <form onSubmit={handleAssignTask} className="flex flex-col gap-3">
              <input
                type="text"
                autoFocus
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                placeholder="Task title (e.g. Add dark mode toggle)"
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground"
                required
              />
              <textarea
                value={taskDesc}
                onChange={(e) => setTaskDesc(e.target.value)}
                placeholder="Description / instructions (optional)"
                rows={3}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground resize-y"
              />
              <div className="flex justify-end gap-2 mt-1">
                <button
                  type="button"
                  onClick={closeAssignPrompt}
                  className="px-4 py-2 rounded-md text-sm font-medium bg-secondary text-secondary-foreground hover:bg-secondary/80"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-2"
                >
                  <Send className="w-4 h-4" /> Assign
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
