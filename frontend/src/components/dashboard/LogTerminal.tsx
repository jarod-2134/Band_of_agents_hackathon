import { useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/useAgentStore';

export function LogTerminal() {
  const logs = useAgentStore((state) => state.logs);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="w-full h-full bg-white border border-border rounded-lg flex flex-col font-mono text-sm overflow-hidden">
      <div className="px-4 py-2 bg-black text-white text-xs font-bold tracking-widest flex justify-between items-center shrink-0">
        <span>TERMINAL OUTPUT</span>
        <span className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          LIVE
        </span>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {logs.length === 0 && (
          <div className="text-muted-foreground italic">Waiting for agent activity...</div>
        )}
        {logs.map((log) => (
          <div key={log.id} className="flex flex-col border-b border-border pb-2 last:border-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-muted-foreground">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              {log.agentRole && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-bold uppercase ${
                  log.agentRole === 'planner' ? 'bg-blue-100 text-blue-700' :
                  log.agentRole === 'engineer' ? 'bg-green-100 text-green-700' :
                  log.agentRole === 'reviewer' ? 'bg-purple-100 text-purple-700' :
                  'bg-orange-100 text-orange-700'
                }`}>
                  {log.agentRole}
                </span>
              )}
            </div>
            <div className={`${
              log.type === 'error' ? 'text-destructive font-bold' :
              log.type === 'action' ? 'text-black font-semibold' :
              'text-black'
            }`}>
              {log.message}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
