import { useState } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { Bot, Play, Plus, UserCog, Settings2 } from 'lucide-react';

export function GraphViewer() {
  const [showManagerForm, setShowManagerForm] = useState(false);
  const [instructions, setInstructions] = useState('');
  const [managerStarted, setManagerStarted] = useState(false);
  
  const addLog = useAgentStore((state) => state.addLog);
  const setGraph = useAgentStore((state) => state.setGraph);
  const nodes = useAgentStore((state) => state.nodes);

  const handleStartManager = () => {
    if (!instructions.trim()) return;
    
    setManagerStarted(true);
    setShowManagerForm(false);
    
    // Send instructions and apiKeys to the backend
    const store = useAgentStore.getState();
    store.sendMessage({ type: "start_manager", instructions, apiKeys: store.apiKeys });
  };

  return (
    <div className="w-full h-full bg-background border border-border rounded-lg p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-border">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Settings2 className="w-6 h-6 text-primary" />
            Agent Orchestration
          </h2>
          <p className="text-muted-foreground text-sm mt-1">Configure and deploy your agent swarm</p>
        </div>
        
        {!managerStarted && !showManagerForm && (
          <button
            onClick={() => setShowManagerForm(true)}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90 transition-colors font-medium text-sm"
          >
            <Plus className="w-4 h-4" /> Add Manager Agent
          </button>
        )}
      </div>

      {showManagerForm && (
        <div className="bg-card p-6 rounded-lg border border-border mb-8 max-w-2xl text-card-foreground">
          <div className="flex items-center gap-3 mb-4 text-lg font-semibold text-foreground">
            <UserCog className="w-5 h-5 text-primary" />
            Configure Manager Agent
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 text-foreground">Manager Instructions</label>
            <textarea
              className="w-full h-32 p-3 border border-border rounded-md resize-none focus:ring-2 focus:ring-ring focus:border-ring outline-none transition-all text-sm bg-background text-foreground"
              placeholder="e.g. Build a new feature for user authentication. You'll need an engineer to write the code and a reviewer to check it..."
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>
          
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setShowManagerForm(false)}
              className="px-4 py-2 text-sm font-medium border rounded-md hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleStartManager}
              disabled={!instructions.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" /> Start Manager
            </button>
          </div>
        </div>
      )}

      {managerStarted && (
        <div className="flex-1 overflow-y-auto p-6 bg-secondary/20">
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="text-sm text-muted-foreground mb-4">
              Active Agents ({nodes?.length || 0})
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {nodes?.map(node => (
                <div key={node.id} className="border border-border rounded-lg p-4 bg-card shadow-sm flex flex-col gap-3 transition-colors hover:border-primary/50">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${node.role === 'planner' ? 'bg-blue-500/20 text-blue-600 dark:text-blue-400' : node.role === 'engineer' ? 'bg-green-500/20 text-green-600 dark:text-green-400' : 'bg-purple-500/20 text-purple-600 dark:text-purple-400'}`}>
                      {node.role === 'planner' ? <Bot className="w-5 h-5" /> : node.role === 'engineer' ? <Code className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                    </div>
                    <div>
                      <h4 className="font-semibold text-foreground text-sm">{node.data.label}</h4>
                      <span className="text-xs text-muted-foreground capitalize">{node.role}</span>
                    </div>
                  </div>
                </div>
              ))}
              
              {(!nodes || nodes.length === 0) && (
                <div className="col-span-full py-12 flex flex-col items-center justify-center text-muted-foreground border border-dashed rounded-lg bg-card/50">
                  <Bot className="w-8 h-8 mb-2 opacity-50" />
                  <p>Manager is analyzing instructions</p>
                  <p className="text-xs opacity-70">Spinning up required agents...</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
