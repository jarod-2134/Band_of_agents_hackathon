import { useMemo, useState } from 'react';
import { useAgentStore } from '@/store/useAgentStore';
import {
  Search,
  Filter,
  Clock3,
  Bot,
  AlertCircle,
  Radio,
  FileText,
} from 'lucide-react';

type HistoryFilter = 'all' | 'agent' | 'band' | 'error';

function getEventCategory(message: string, type: string) {
  const lower = message.toLowerCase();

  if (type === 'error') return 'error';
  if (lower.includes('band') || lower.includes('handoff') || lower.includes('payload')) return 'band';
  return 'agent';
}

function getDisplayRole(message: string, agentRole?: string) {
  const lower = message.toLowerCase();

  if (lower.includes('band')) return 'Band';
  if (lower.includes('developer')) return 'Developer Agent';
  if (lower.includes('reviewer')) return 'Reviewer Agent';
  if (lower.includes('qa') || lower.includes('tester')) return 'QA Agent';
  if (lower.includes('pm') || lower.includes('manager') || lower.includes('planner')) return 'PM Agent';

  if (agentRole) {
    if (agentRole === 'engineer') return 'Developer Agent';
    if (agentRole === 'tester') return 'QA Agent';
    return `${agentRole[0].toUpperCase()}${agentRole.slice(1)} Agent`;
  }

  return 'System';
}

export function TaskHistory() {
  const logs = useAgentStore((state) => state.logs);
  const nodes = useAgentStore((state) => state.nodes);
  const fileTree = useAgentStore((state) => state.fileTree);
  const isConnected = useAgentStore((state) => state.isConnected);

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<HistoryFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const events = useMemo(() => {
    return logs
      .filter((log) => !log.message.toLowerCase().includes('websocket disconnected'))
      .map((log) => {
        const category = getEventCategory(log.message, log.type);
        const role = getDisplayRole(log.message, log.agentRole);

        return {
          id: log.id,
          timestamp: log.timestamp,
          time: new Date(log.timestamp).toLocaleTimeString(),
          date: new Date(log.timestamp).toLocaleDateString(),
          message: log.message,
          type: log.type,
          category,
          role,
        };
      })
      .sort((a, b) => b.timestamp - a.timestamp);
  }, [logs]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      const matchesSearch =
        event.message.toLowerCase().includes(search.toLowerCase()) ||
        event.role.toLowerCase().includes(search.toLowerCase()) ||
        event.category.toLowerCase().includes(search.toLowerCase());

      const matchesFilter = filter === 'all' || event.category === filter;

      return matchesSearch && matchesFilter;
    });
  }, [events, search, filter]);

  const selectedEvent = filteredEvents.find((event) => event.id === selectedId) ?? filteredEvents[0];

  return (
    <div className="flex-1 overflow-y-auto bg-background p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-start justify-between gap-6 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Workflow History</h1>
            <p className="text-muted-foreground mt-1">
              Review agent activity, handoffs, and workflow events recorded in this workspace session.
            </p>
          </div>

          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            {isConnected ? 'Connected' : 'Disconnected'}
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search workflow history..."
              className="w-full pl-9 pr-3 py-2 rounded-md border border-border bg-card text-foreground outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex gap-2">
            {(['all', 'agent', 'band', 'error'] as HistoryFilter[]).map((item) => (
              <button
                key={item}
                onClick={() => setFilter(item)}
                className={`px-3 py-2 rounded-md border text-sm font-medium capitalize flex items-center gap-2 ${
                  filter === item
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-card text-foreground border-border hover:bg-secondary'
                }`}
              >
                <Filter className="w-4 h-4" />
                {item}
              </button>
            ))}
          </div>
        </div>

        {filteredEvents.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg bg-card p-12 text-center">
            <Clock3 className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <h2 className="font-semibold text-foreground">No workflow history yet</h2>
            <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto">
              Run a workflow from the Agents page to populate this timeline with agent events and Band handoffs.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-6">
            <div className="border border-border bg-card rounded-lg overflow-hidden">
              <div className="px-5 py-3 border-b border-border text-xs font-bold tracking-widest text-muted-foreground">
                ACTIVITY TIMELINE
              </div>

              <div className="divide-y divide-border">
                {filteredEvents.map((event) => (
                  <button
                    key={event.id}
                    onClick={() => setSelectedId(event.id)}
                    className={`w-full text-left p-4 hover:bg-secondary/60 transition-colors ${
                      selectedEvent?.id === event.id ? 'bg-secondary' : ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${
                          event.category === 'error'
                            ? 'bg-red-500/10 text-red-600'
                            : event.category === 'band'
                              ? 'bg-blue-500/10 text-blue-600'
                              : 'bg-primary/10 text-primary'
                        }`}
                      >
                        {event.category === 'error' ? (
                          <AlertCircle className="w-5 h-5" />
                        ) : event.category === 'band' ? (
                          <Radio className="w-5 h-5" />
                        ) : (
                          <Bot className="w-5 h-5" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-semibold text-sm text-foreground">{event.role}</div>
                          <div className="text-xs text-muted-foreground">{event.time}</div>
                        </div>

                        <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {event.message}
                        </div>

                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-secondary text-secondary-foreground capitalize">
                            {event.category}
                          </span>
                          <span className="text-[11px] text-muted-foreground">{event.date}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="border border-border bg-card rounded-lg p-5 h-fit sticky top-4">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Selected event
              </div>

              {selectedEvent ? (
                <>
                  <h2 className="text-lg font-bold text-foreground">{selectedEvent.role}</h2>
                  <p className="text-sm text-muted-foreground mt-1">
                    {selectedEvent.date} · {selectedEvent.time}
                  </p>

                  <div className="my-5 border-t border-border" />

                  <div className="space-y-4">
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Event type</div>
                      <div className="text-sm font-medium text-foreground capitalize">
                        {selectedEvent.category}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Message</div>
                      <div className="text-sm text-foreground leading-relaxed">
                        {selectedEvent.message}
                      </div>
                    </div>

                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Workspace snapshot</div>
                      <div className="space-y-2 text-sm text-foreground">
                        <div className="flex items-center gap-2">
                          <Bot className="w-4 h-4 text-muted-foreground" />
                          Active graph nodes: {nodes.length}
                        </div>
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-muted-foreground" />
                          Root files/folders: {fileTree.length}
                        </div>
                      </div>
                    </div>

                    {selectedEvent.category === 'band' && (
                      <div className="p-4 rounded-lg border border-dashed border-border bg-secondary/30">
                        <div className="text-xs text-muted-foreground mb-2">
                          Band coordination event
                        </div>
                        <div className="text-sm text-foreground">
                          This event represents a handoff or structured context transfer between agents.
                        </div>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="text-sm text-muted-foreground">Select an event to inspect it.</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}