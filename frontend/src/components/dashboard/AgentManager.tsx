import { useState, useEffect } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { Bot, Play, Square, Plus, Trash2, Send } from 'lucide-react';

export function AgentManager() {
  const currentOrgSlug = useAgentStore((state) => state.currentOrgSlug) || 'jarod-2134';
  const [agents, setAgents] = useState<any[]>([]);
  const [newName, setNewName] = useState('');
  const [newModel, setNewModel] = useState('gpt-4o');

  const fetchAgents = () => {
    fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents`)
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
      const res = await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
    try {
      await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents/${id}/start?band_agent_id=dummy&band_agent_api_key=dummy`, {
        method: 'POST'
      });
      fetchAgents();
    } catch (err) {
      console.error(err);
    }
  };

  const handleStop = async (id: number) => {
    try {
      await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents/${id}/stop`, {
        method: 'POST'
      });
      fetchAgents();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this agent?')) return;
    try {
      await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents/${id}`, {
        method: 'DELETE'
      });
      fetchAgents();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAssignTask = async (id: number) => {
    const taskId = prompt("Enter Task ID (UUID):", crypto.randomUUID());
    if (!taskId) return;
    try {
      const res = await fetch(`http://localhost:8000/orgs/${currentOrgSlug}/agents/${id}/assign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_id: taskId })
      });
      if (res.ok) {
        alert("Task assigned successfully!");
        fetchAgents();
      } else {
        const err = await res.json();
        alert(`Failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error(err);
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
            <input 
              type="text" 
              value={newModel}
              onChange={e => setNewModel(e.target.value)}
              className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            />
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
                className="absolute top-4 right-4 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
                title="Delete Agent"
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
                  onClick={() => handleAssignTask(agent.id)}
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
    </div>
  );
}
