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
    <div className="w-full h-full bg-white border border-border rounded-lg p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-8 pb-4 border-b">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Settings2 className="w-6 h-6 text-blue-600" />
            Agent Orchestration
          </h2>
          <p className="text-muted-foreground text-sm mt-1">Configure and deploy your agent swarm</p>
        </div>
        
        {!managerStarted && !showManagerForm && (
          <button
            onClick={() => setShowManagerForm(true)}
            className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded-md hover:bg-neutral-800 transition-colors font-medium text-sm"
          >
            <Plus className="w-4 h-4" /> Add Manager Agent
          </button>
        )}
      </div>

      {showManagerForm && (
        <div className="bg-neutral-50 p-6 rounded-lg border mb-8 max-w-2xl">
          <div className="flex items-center gap-3 mb-4 text-lg font-semibold">
            <UserCog className="w-5 h-5 text-indigo-600" />
            Configure Manager Agent
          </div>
          
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2 text-neutral-700">Manager Instructions</label>
            <textarea
              className="w-full h-32 p-3 border rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all text-sm"
              placeholder="e.g. Build a new feature for user authentication. You'll need an engineer to write the code and a reviewer to check it..."
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>
          
          <div className="flex justify-end gap-3">
            <button
              onClick={() => setShowManagerForm(false)}
              className="px-4 py-2 text-sm font-medium border rounded-md hover:bg-neutral-100 transition-colors bg-white"
            >
              Cancel
            </button>
            <button
              onClick={handleStartManager}
              disabled={!instructions.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Play className="w-4 h-4" /> Start Manager
            </button>
          </div>
        </div>
      )}

      {managerStarted && (
        <div className="space-y-6">
          <div className="flex items-center gap-2 text-lg font-semibold border-b pb-2">
            <Bot className="w-5 h-5" /> Active Agents
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodes?.map(node => (
              <div key={node.id} className="border rounded-lg p-4 bg-white shadow-sm flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${node.role === 'planner' ? 'bg-indigo-100 text-indigo-600' : node.role === 'engineer' ? 'bg-blue-100 text-blue-600' : 'bg-emerald-100 text-emerald-600'}`}>
                    {node.role === 'planner' ? <UserCog className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                  </div>
                  <div>
                    <div className="font-semibold">{node.data.label}</div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wider">{node.role}</div>
                  </div>
                </div>
                <div className="text-sm bg-neutral-50 p-2 rounded border border-neutral-100 text-neutral-600">
                  {node.role === 'planner' ? 'Orchestrating tasks...' : node.role === 'engineer' ? 'Writing implementation...' : 'Reviewing code...'}
                </div>
              </div>
            ))}
            
            {nodes.length === 1 && (
              <div className="border rounded-lg p-4 bg-neutral-50 border-dashed flex items-center justify-center text-muted-foreground text-sm text-center">
                Manager is analyzing instructions<br/>and spinning up required agents...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
