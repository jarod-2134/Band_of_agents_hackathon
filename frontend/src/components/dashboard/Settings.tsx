import { Save } from 'lucide-react';

export function Settings() {
  return (
    <div className="flex-1 overflow-y-auto p-8 bg-white h-full">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8 border-b pb-4">
          <h1 className="text-2xl font-bold text-neutral-900">Settings</h1>
          <p className="text-neutral-500 mt-1">Configure global parameters for your agent swarm.</p>
        </div>

        <div className="space-y-8">
          
          {/* Models Configuration */}
          <section className="border rounded-lg p-6 bg-neutral-50/50">
            <h2 className="text-lg font-semibold mb-4 text-neutral-800">Model Configuration</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-neutral-700">Default LLM Model</label>
                <select className="w-full max-w-md p-2.5 border rounded-md bg-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm">
                  <option>gpt-4o</option>
                  <option>claude-3-5-sonnet-20240620</option>
                  <option>gemini-1.5-pro</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-1.5 text-neutral-700">Temperature</label>
                <div className="flex items-center gap-4 max-w-md">
                  <input type="range" min="0" max="1" step="0.1" defaultValue="0.2" className="flex-1" />
                  <span className="text-sm font-mono text-neutral-600 bg-white px-2 py-1 border rounded">0.2</span>
                </div>
                <p className="text-xs text-neutral-500 mt-2">Lower values produce more deterministic code outputs.</p>
              </div>
            </div>
          </section>

          {/* System Instructions */}
          <section className="border rounded-lg p-6 bg-neutral-50/50">
            <h2 className="text-lg font-semibold mb-4 text-neutral-800">Global System Instructions</h2>
            <p className="text-sm text-neutral-500 mb-3">These instructions are prepended to every agent's context window.</p>
            <textarea 
              className="w-full h-32 p-3 border rounded-md resize-y focus:ring-2 focus:ring-indigo-500 outline-none text-sm font-mono bg-white"
              defaultValue="You are an expert software engineering swarm. Always write clean, well-documented, and tested code. Prefer TypeScript over JavaScript. Prioritize performance and readability."
            />
          </section>

          {/* API Keys */}
          <section className="border rounded-lg p-6 bg-neutral-50/50">
            <h2 className="text-lg font-semibold mb-4 text-neutral-800">API Keys</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1.5 text-neutral-700">OpenAI API Key</label>
                <input type="password" placeholder="sk-..." className="w-full max-w-md p-2.5 border rounded-md bg-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-neutral-700">Anthropic API Key</label>
                <input type="password" placeholder="sk-ant-..." className="w-full max-w-md p-2.5 border rounded-md bg-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5 text-neutral-700">GitHub Token (for PRs)</label>
                <input type="password" placeholder="ghp_..." className="w-full max-w-md p-2.5 border rounded-md bg-white focus:ring-2 focus:ring-indigo-500 outline-none text-sm" />
              </div>
            </div>
          </section>

          <div className="flex justify-end pt-4">
            <button className="flex items-center gap-2 bg-indigo-600 text-white px-6 py-2.5 rounded-md hover:bg-indigo-700 transition-colors font-medium text-sm">
              <Save className="w-4 h-4" /> Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
