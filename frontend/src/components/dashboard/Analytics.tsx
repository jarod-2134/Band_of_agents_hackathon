import { useMemo } from 'react';
import { useAgentStore, type FileNode } from '@/store/useAgentStore';
import {
  Clock,
  Activity,
  Bot,
  AlertCircle,
  Database,
  GitBranch,
  Radio,
  Code,
  CheckCircle2,
} from 'lucide-react';

function flattenFiles(nodes: FileNode[]): FileNode[] {
  return nodes.flatMap((node) => {
    if (node.children) {
      return [node, ...flattenFiles(node.children)];
    }

    return [node];
  });
}

function inferRole(message: string, agentRole?: string) {
  const lower = message.toLowerCase();

  if (lower.includes('band')) return 'Band';
  if (lower.includes('developer') || agentRole === 'engineer') return 'Developer';
  if (lower.includes('reviewer') || agentRole === 'reviewer') return 'Reviewer';
  if (lower.includes('qa') || lower.includes('tester') || agentRole === 'tester') return 'QA';
  if (lower.includes('pm') || lower.includes('manager') || agentRole === 'planner') return 'PM';

  return 'System';
}

export function Analytics() {
  const logs = useAgentStore((state) => state.logs);
  const nodes = useAgentStore((state) => state.nodes);
  const edges = useAgentStore((state) => state.edges);
  const fileTree = useAgentStore((state) => state.fileTree);

  const cleanLogs = useMemo(() => {
    return logs.filter((log) => !log.message.toLowerCase().includes('websocket disconnected'));
  }, [logs]);

  const allFiles = useMemo(() => flattenFiles(fileTree), [fileTree]);

  const modifiedFiles = allFiles.filter((file) => file.status === 'modified');
  const errorEvents = cleanLogs.filter((log) => log.type === 'error');
  const bandEvents = cleanLogs.filter((log) => {
    const lower = log.message.toLowerCase();
    return lower.includes('band') || lower.includes('handoff') || lower.includes('payload');
  });

  const roleBreakdown = useMemo(() => {
    const roles = ['PM', 'Developer', 'Reviewer', 'QA', 'Band', 'System'];

    return roles.map((role) => {
      const count = cleanLogs.filter((log) => inferRole(log.message, log.agentRole) === role).length;
      return { role, count };
    });
  }, [cleanLogs]);

  const maxRoleCount = Math.max(...roleBreakdown.map((item) => item.count), 1);

  const recentEvents = cleanLogs
    .slice(-6)
    .reverse()
    .map((log) => ({
      id: log.id,
      role: inferRole(log.message, log.agentRole),
      message: log.message,
      time: new Date(log.timestamp).toLocaleTimeString(),
      type: log.type,
    }));

  const successRate =
    cleanLogs.length === 0
      ? 0
      : Math.round(((cleanLogs.length - errorEvents.length) / cleanLogs.length) * 100);

  const cards = [
    {
      label: 'Agent events',
      value: cleanLogs.length,
      description: 'Recorded activity logs',
      icon: Activity,
    },
    {
      label: 'Active agents',
      value: nodes.length,
      description: 'Current graph nodes',
      icon: Bot,
    },
    {
      label: 'Band handoffs',
      value: bandEvents.length,
      description: 'Detected context transfers',
      icon: Radio,
    },
    {
      label: 'Modified files',
      value: modifiedFiles.length,
      description: 'Changed workspace files',
      icon: Code,
    },
    {
      label: 'Graph edges',
      value: edges.length,
      description: 'Agent coordination links',
      icon: GitBranch,
    },
    {
      label: 'Files indexed',
      value: allFiles.length,
      description: 'Files and folders tracked',
      icon: Database,
    },
  ];

  return (
    <div className="flex-1 overflow-y-auto bg-background p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-start justify-between gap-6 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Analytics</h1>
            <p className="text-muted-foreground mt-1">
              Monitor agent activity, Band handoffs, workspace changes, and session health.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
          {cards.map((card) => {
            const Icon = card.icon;

            return (
              <div key={card.label} className="border border-border bg-card rounded-lg p-4">
                <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>

                <div className="text-2xl font-bold text-foreground mt-4">{card.value}</div>
                <div className="text-sm font-medium text-foreground mt-1">{card.label}</div>
                <div className="text-xs text-muted-foreground mt-1">{card.description}</div>
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
          <div className="space-y-6">
            <div className="border border-border bg-card rounded-lg p-6">
              <h2 className="text-lg font-bold text-foreground">Agent activity by role</h2>
              <p className="text-sm text-muted-foreground mt-1 mb-6">
                Breakdown of recorded activity across agents and coordination layer.
              </p>

              {cleanLogs.length === 0 ? (
                <div className="border border-dashed border-border rounded-lg p-10 text-center">
                  <Clock className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
                  <div className="font-semibold text-foreground">No activity yet</div>
                  <p className="text-sm text-muted-foreground mt-2">
                    Once agents produce logs, this chart will update automatically.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {roleBreakdown.map((item) => (
                    <div key={item.role}>
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span className="font-medium text-foreground">{item.role}</span>
                        <span className="text-muted-foreground">{item.count}</span>
                      </div>

                      <div className="h-3 rounded-full bg-secondary overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${(item.count / maxRoleCount) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border border-border bg-card rounded-lg p-6">
              <h2 className="text-lg font-bold text-foreground mb-4">Recent activity</h2>

              {recentEvents.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  No recent agent activity has been recorded.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {recentEvents.map((event) => (
                    <div key={event.id} className="py-3 flex items-start gap-3">
                      <div
                        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                          event.type === 'error'
                            ? 'bg-red-500/10 text-red-600'
                            : 'bg-primary/10 text-primary'
                        }`}
                      >
                        {event.type === 'error' ? (
                          <AlertCircle className="w-4 h-4" />
                        ) : (
                          <Bot className="w-4 h-4" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-foreground">{event.role}</div>
                          <div className="text-xs text-muted-foreground">{event.time}</div>
                        </div>

                        <div className="text-sm text-muted-foreground mt-1">{event.message}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="border border-border bg-card rounded-lg p-6">
              <h2 className="text-lg font-bold text-foreground mb-5">Session health</h2>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Success rate</span>
                  <span className="font-bold text-foreground">{successRate}%</span>
                </div>

                <div className="h-3 rounded-full bg-secondary overflow-hidden">
                  <div className="h-full bg-green-500 rounded-full" style={{ width: `${successRate}%` }} />
                </div>

                <div className="pt-4 border-t border-border space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <CheckCircle2 className="w-4 h-4" />
                      Non-error events
                    </span>
                    <span className="font-medium text-foreground">
                      {Math.max(cleanLogs.length - errorEvents.length, 0)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <AlertCircle className="w-4 h-4" />
                      Error events
                    </span>
                    <span className="font-medium text-foreground">{errorEvents.length}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="border border-border bg-card rounded-lg p-6">
              <h2 className="text-lg font-bold text-foreground mb-5">Modified files</h2>

              {modifiedFiles.length === 0 ? (
                <div className="text-sm text-muted-foreground">
                  No modified files are currently recorded in the workspace.
                </div>
              ) : (
                <div className="space-y-2">
                  {modifiedFiles.map((file) => (
                    <div key={file.path} className="font-mono text-xs text-foreground">
                      {file.path}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border border-border bg-card rounded-lg p-6">
              <h2 className="text-lg font-bold text-foreground mb-5">Error summary</h2>

              {errorEvents.length === 0 ? (
                <div className="text-sm text-muted-foreground">No errors recorded.</div>
              ) : (
                <div className="space-y-3">
                  {errorEvents.slice(-4).map((event) => (
                    <div key={event.id} className="text-sm text-foreground">
                      {event.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}