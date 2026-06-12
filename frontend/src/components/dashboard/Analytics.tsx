import { Activity, Zap, Clock, Code2 } from 'lucide-react';

export function Analytics() {
  return (
    <div className="flex-1 overflow-y-auto p-8 bg-background h-full text-foreground">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8 border-b border-border pb-4">
          <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
          <p className="text-muted-foreground mt-1">Monitor swarm performance, costs, and activity.</p>
        </div>

        {/* Top KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="border border-border rounded-xl p-5 bg-card">
            <div className="flex items-center gap-3 text-muted-foreground mb-2">
              <Activity className="w-5 h-5 text-blue-500" />
              <span className="text-sm font-medium">Total Tasks Run</span>
            </div>
            <div className="text-3xl font-bold text-foreground">1,284</div>
            <div className="text-xs text-green-500 mt-2 font-medium">+12% from last week</div>
          </div>
          
          <div className="border border-border rounded-xl p-5 bg-card">
            <div className="flex items-center gap-3 text-muted-foreground mb-2">
              <Zap className="w-5 h-5 text-yellow-500" />
              <span className="text-sm font-medium">Success Rate</span>
            </div>
            <div className="text-3xl font-bold text-foreground">94.2%</div>
            <div className="text-xs text-green-500 mt-2 font-medium">+1.1% from last week</div>
          </div>

          <div className="border border-border rounded-xl p-5 bg-card">
            <div className="flex items-center gap-3 text-muted-foreground mb-2">
              <Clock className="w-5 h-5 text-indigo-500" />
              <span className="text-sm font-medium">Avg Execution Time</span>
            </div>
            <div className="text-3xl font-bold text-foreground">45s</div>
            <div className="text-xs text-red-500 mt-2 font-medium">+5s from last week</div>
          </div>

          <div className="border border-border rounded-xl p-5 bg-card">
            <div className="flex items-center gap-3 text-muted-foreground mb-2">
              <Code2 className="w-5 h-5 text-emerald-500" />
              <span className="text-sm font-medium">Lines of Code Written</span>
            </div>
            <div className="text-3xl font-bold text-foreground">14.5k</div>
            <div className="text-xs text-green-500 mt-2 font-medium">+3.2k from last week</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Mock Chart Area */}
          <div className="lg:col-span-2 border border-border rounded-xl p-6 bg-card shadow-sm">
            <h2 className="text-lg font-semibold mb-6 text-foreground">Token Usage (Last 7 Days)</h2>
            <div className="h-64 flex items-end justify-between gap-2">
              {[40, 65, 35, 80, 55, 90, 70].map((height, i) => (
                <div key={i} className="w-full bg-primary/20 rounded-t-sm relative group cursor-pointer" style={{ height: `${height}%` }}>
                  <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 bg-popover text-popover-foreground text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
                    {height * 1000} tokens
                  </div>
                  <div className="w-full h-full bg-primary rounded-t-sm opacity-80 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 text-xs text-muted-foreground font-medium">
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i]}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cost Breakdown */}
          <div className="border border-border rounded-xl p-6 bg-card shadow-sm">
            <h2 className="text-lg font-semibold mb-6 text-foreground">Cost Breakdown</h2>
            <div className="space-y-6">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-muted-foreground">Manager Agent (GPT-4o)</span>
                  <span className="font-bold text-foreground">$42.50</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-primary w-[60%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-muted-foreground">Engineer Agent (Claude 3.5)</span>
                  <span className="font-bold text-foreground">$21.80</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-accent w-[30%]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-medium text-muted-foreground">Reviewer Agent (GPT-4o Mini)</span>
                  <span className="font-bold text-foreground">$6.20</span>
                </div>
                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 w-[10%]" />
                </div>
              </div>

              <div className="pt-6 mt-6 border-t border-border flex justify-between items-center">
                <span className="text-muted-foreground font-medium">Total Estimated Cost</span>
                <span className="text-2xl font-bold text-foreground">$70.50</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
