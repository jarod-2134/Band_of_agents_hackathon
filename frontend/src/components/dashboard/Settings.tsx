import { Save } from 'lucide-react';
import { useAgentStore } from '@/store/useAgentStore';

export function Settings() {
  const { apiKeys, setApiKey, theme, setTheme } = useAgentStore();

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-background h-full text-foreground">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 border-b border-border pb-4">
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-muted-foreground mt-1">Configure global parameters for your agent swarm.</p>
        </div>

        <div className="space-y-8">

          {/* Appearance Configuration */}
          <section className="border border-border rounded-lg p-6 bg-card text-card-foreground">
            <h2 className="text-lg font-semibold mb-4 text-foreground">Appearance</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Theme</label>
                <div className="flex flex-wrap gap-4">
                  {['light', 'dark', 'cyberpunk', 'ocean', 'forest'].map((t) => (
                    <button 
                      key={t}
                      onClick={() => setTheme(t)}
                      className={`px-4 py-2 border rounded-md text-sm font-medium capitalize ${theme === t ? 'bg-primary text-primary-foreground border-primary' : 'bg-background text-foreground border-border hover:bg-secondary'}`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>
          
          {/* Models Configuration */}
          <section className="border border-border rounded-lg p-6 bg-card text-card-foreground">
            <h2 className="text-lg font-semibold mb-4 text-foreground">Model Configuration</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Default LLM Model</label>
                <select className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm">
                  <option>gpt-4o</option>
                  <option>claude-3-5-sonnet-20240620</option>
                  <option>gemini-1.5-pro</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Temperature</label>
                <div className="flex items-center gap-4 max-w-md">
                  <input type="range" min="0" max="1" step="0.1" defaultValue="0.2" className="flex-1 accent-primary" />
                  <span className="text-sm font-mono text-foreground bg-background px-2 py-1 border border-border rounded">0.2</span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">Lower values produce more deterministic code outputs.</p>
              </div>
            </div>
          </section>

          {/* System Instructions */}
          <section className="border border-border rounded-lg p-6 bg-card text-card-foreground">
            <h2 className="text-lg font-semibold mb-4 text-foreground">Global System Instructions</h2>
            <p className="text-sm text-muted-foreground mb-3">These instructions are prepended to every agent's context window.</p>
            <textarea 
              className="w-full h-32 p-3 border border-border rounded-md resize-y focus:ring-2 focus:ring-primary outline-none text-sm font-mono bg-background text-foreground"
              defaultValue="You are an expert software engineering swarm. Always write clean, well-documented, and tested code. Prefer TypeScript over JavaScript. Prioritize performance and readability."
            />
          </section>

          {/* API Keys */}
          <section className="border border-border rounded-lg p-6 bg-card text-card-foreground">
            <h2 className="text-lg font-semibold mb-4 text-foreground">API Keys</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Band AI API Key</label>
                <input 
                  type="password" 
                  placeholder="band-..." 
                  className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm blur-sm focus:blur-none hover:blur-none transition-all" 
                  value={apiKeys['bandai'] || ''}
                  onChange={(e) => setApiKey('bandai', e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">Key for https://app.band.ai to access all multi-models.</p>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Band Agent ID (UUID)</label>
                <input 
                  type="text" 
                  placeholder="00000000-0000-0000-0000-000000000000" 
                  className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm" 
                  value={apiKeys['band_agent_id'] || ''}
                  onChange={(e) => setApiKey('band_agent_id', e.target.value)}
                />
                <p className="text-xs text-muted-foreground mt-1">The unique Agent UUID from https://app.band.ai.</p>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">OpenAI API Key</label>
                <input 
                  type="password" 
                  placeholder="sk-..." 
                  className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm blur-sm focus:blur-none hover:blur-none transition-all" 
                  value={apiKeys['openai'] || ''}
                  onChange={(e) => setApiKey('openai', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">Anthropic API Key</label>
                <input 
                  type="password" 
                  placeholder="sk-ant-..." 
                  className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm blur-sm focus:blur-none hover:blur-none transition-all" 
                  value={apiKeys['anthropic'] || ''}
                  onChange={(e) => setApiKey('anthropic', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-foreground">GitHub Token (for PRs)</label>
                <input 
                  type="password" 
                  placeholder="ghp_..." 
                  className="w-full max-w-md p-2.5 border border-border rounded-md bg-background text-foreground focus:ring-2 focus:ring-primary outline-none text-sm blur-sm focus:blur-none hover:blur-none transition-all" 
                  value={apiKeys['github'] || ''}
                  onChange={(e) => setApiKey('github', e.target.value)}
                />
              </div>
            </div>
          </section>

          <div className="flex justify-end pt-4">
            <button className="flex items-center gap-2 bg-primary text-primary-foreground px-6 py-2.5 rounded-md hover:opacity-90 transition-opacity font-medium text-sm">
              <Save className="w-4 h-4" /> Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
