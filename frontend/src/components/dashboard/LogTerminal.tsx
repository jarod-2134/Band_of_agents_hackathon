import { useEffect, useRef } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import { ChevronDown, ChevronRight } from 'lucide-react';

type LogTerminalProps = {
  isOpen: boolean;
  onToggle: () => void;
};

const mockActivity = [
  {
    time: '03:56:21',
    role: 'PM Agent',
    message: 'Created implementation brief for “Build login page”.',
  },
  {
    time: '03:56:24',
    role: 'Band',
    message: 'Delivered structured handoff payload to Developer Agent.',
  },
  {
    time: '03:56:31',
    role: 'Developer Agent',
    message: 'Started editing Login.tsx and auth.ts.',
  },
  {
    time: '03:56:42',
    role: 'Reviewer Agent',
    message: 'Waiting for code review request.',
  },
];

export function LogTerminal({ isOpen, onToggle }: LogTerminalProps) {
  const logs = useAgentStore((state) => state.logs);
  const bottomRef = useRef<HTMLDivElement>(null);

  const usefulLogs = logs.filter((log) => !log.message.toLowerCase().includes('websocket disconnected'));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="w-full h-full bg-card text-card-foreground border border-border rounded-lg flex flex-col font-mono text-sm overflow-hidden shadow-sm">
      <button
        onClick={onToggle}
        className="px-4 py-2 bg-secondary border-b border-border text-secondary-foreground text-xs font-bold tracking-widest flex justify-between items-center shrink-0 hover:bg-secondary/80 transition-colors"
      >
        <span className="flex items-center gap-2">
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          AGENT ACTIVITY
        </span>

        <span className="flex items-center gap-2 text-muted-foreground">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          DEMO
        </span>
      </button>

      {isOpen && (
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {usefulLogs.length === 0 &&
            mockActivity.map((log) => (
              <div key={`${log.time}-${log.message}`} className="flex flex-col border-b border-border pb-2 last:border-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-muted-foreground">{log.time}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full font-bold uppercase bg-primary/10 text-primary">
                    {log.role}
                  </span>
                </div>
                <div className="text-foreground">{log.message}</div>
              </div>
            ))}

          {usefulLogs.map((log) => (
            <div key={log.id} className="flex flex-col border-b border-border pb-2 last:border-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-muted-foreground">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                {log.agentRole && (
                  <span className="text-xs px-2 py-0.5 rounded-full font-bold uppercase bg-primary/10 text-primary">
                    {log.agentRole}
                  </span>
                )}
              </div>
              <div className="text-foreground">{log.message}</div>
            </div>
          ))}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}