import { useMemo, useState } from 'react';
import { useAgentStore, type FileNode, type GraphEdge, type GraphNode, type LogEntry } from '@/store/useAgentStore';
import {
  Settings2,
  ClipboardList,
  UserCog,
  Code,
  SearchCheck,
  ShieldCheck,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Loader2,
  Radio,
  PlusCircle,
} from 'lucide-react';
import { AgentNetworkGraph } from './AgentNetworkGraph';
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { SortableTaskItem } from './SortableTaskItem';

const demoFileTree: FileNode[] = [
  {
    name: 'frontend',
    path: 'frontend',
    isDir: true,
    children: [
      { name: 'Login.tsx', path: 'frontend/src/Login.tsx', isDir: false, status: 'modified' },
      { name: 'auth.ts', path: 'frontend/src/auth.ts', isDir: false, status: 'modified' },
      { name: 'Dashboard.tsx', path: 'frontend/src/components/dashboard/Dashboard.tsx', isDir: false },
      { name: 'GraphViewer.tsx', path: 'frontend/src/components/dashboard/GraphViewer.tsx', isDir: false },
    ],
  },
  {
    name: 'backend',
    path: 'backend',
    isDir: true,
    children: [
      { name: 'agents.py', path: 'backend/agents/corporate.py', isDir: false },
      { name: 'main.py', path: 'backend/main.py', isDir: false },
    ],
  },
  { name: 'README.md', path: 'README.md', isDir: false },
];

const demoNodes: GraphNode[] = [
  { id: 'pm', data: { label: 'PM Agent' }, role: 'planner' },
  { id: 'developer', data: { label: 'Developer Agent' }, role: 'engineer' },
  { id: 'reviewer', data: { label: 'Reviewer Agent' }, role: 'reviewer' },
  { id: 'qa', data: { label: 'QA Agent' }, role: 'tester' },
];

const demoEdges: GraphEdge[] = [
  { id: 'pm-developer', source: 'pm', target: 'developer', animated: true },
  { id: 'developer-reviewer', source: 'developer', target: 'reviewer', animated: true },
  { id: 'reviewer-qa', source: 'reviewer', target: 'qa', animated: true },
  { id: 'qa-pm', source: 'qa', target: 'pm', animated: true },
];

function createDemoLogs(): LogEntry[] {
  const base = Date.now();

  return [
    {
      id: 'demo-1',
      timestamp: base,
      type: 'action',
      agentRole: 'planner',
      message: 'PM Agent created implementation brief for “Build login page”.',
    },
    {
      id: 'demo-2',
      timestamp: base + 1200,
      type: 'action',
      message: 'Band handoff: Delivered structured task payload from PM Agent to Developer Agent.',
    },
    {
      id: 'demo-3',
      timestamp: base + 2400,
      type: 'action',
      agentRole: 'engineer',
      message: 'Developer Agent modified Login.tsx and auth.ts.',
    },
    {
      id: 'demo-4',
      timestamp: base + 3600,
      type: 'action',
      message: 'Band handoff: Developer Agent sent review request payload to Reviewer Agent.',
    },
    {
      id: 'demo-5',
      timestamp: base + 4800,
      type: 'action',
      agentRole: 'reviewer',
      message: 'Reviewer Agent approved authentication flow and requested QA verification.',
    },
    {
      id: 'demo-6',
      timestamp: base + 6000,
      type: 'action',
      message: 'Band handoff: Reviewer Agent sent QA verification payload to QA Agent.',
    },
    {
      id: 'demo-7',
      timestamp: base + 7200,
      type: 'action',
      agentRole: 'tester',
      message: 'QA Agent passed workflow checks for login validation and submit state.',
    },
    {
      id: 'demo-8',
      timestamp: base + 8400,
      type: 'action',
      message: 'Band handoff: QA Agent sent final completion report to PM Agent.',
    },
  ];
}

const demoTasks = [
  {
    id: 1,
    title: 'Build login page',
    owner: 'QA Agent',
    status: 'Completed',
    priority: 'High',
    journey: [
      {
        agent: 'PM Agent',
        role: 'Planning',
        status: 'Completed',
        icon: UserCog,
        description: 'Broke the request into implementation steps and acceptance criteria.',
        output: 'Created task brief and handed it off to Developer Agent through Band.',
      },
      {
        agent: 'Developer Agent',
        role: 'Implementation',
        status: 'Completed',
        icon: Code,
        description: 'Implemented the login UI, validation, and submit loading state.',
        output: 'Modified Login.tsx and auth.ts, then sent a review request through Band.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Review',
        status: 'Completed',
        icon: SearchCheck,
        description: 'Reviewed auth edge cases, code quality, and error handling.',
        output: 'Approved the changes and handed the task off to QA Agent through Band.',
      },
      {
        agent: 'QA Agent',
        role: 'Testing',
        status: 'Completed',
        icon: ShieldCheck,
        description: 'Verified login validation, submit state, and failure behavior.',
        output: 'Sent final completion report back through Band.',
      },
    ],
    bandContext: {
      from: 'QA Agent',
      to: 'PM Agent',
      type: 'completion_report',
      brief: 'Login workflow passed QA checks and is ready to close.',
      criteria: ['Email validation works', 'Password validation works', 'Loading state appears', 'Invalid login errors are visible'],
      files: ['frontend/src/Login.tsx', 'frontend/src/auth.ts'],
      next: 'PM Agent → Done',
      nextPayload: 'Close task and include result in workflow history.',
    },
  },
];

export function GraphViewer() {
  const demoMode = useAgentStore((state) => state.demoMode);
  const nodes = useAgentStore((state) => state.nodes);
  const startDemoSession = useAgentStore((state) => state.startDemoSession);
  const stopDemoSession = useAgentStore((state) => state.stopDemoSession);

  const setTasks = useAgentStore((state) => state.setTasks);
  const addTask = useAgentStore((state) => state.addTask);
  const tasks = useAgentStore((state) => state.tasks);
  const [selectedTask, setSelectedTask] = useState(demoTasks[0]);
  const [newTaskTitle, setNewTaskTitle] = useState('');

  const liveAgentCount = useMemo(() => nodes.length, [nodes]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = tasks.findIndex((t) => t.id === active.id);
      const newIndex = tasks.findIndex((t) => t.id === over.id);
      setTasks(arrayMove(tasks, oldIndex, newIndex));
    }
  };

  const handleAddTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    
    addTask({
      id: `task-${Date.now()}`,
      title: newTaskTitle.trim(),
      owner: 'Unassigned',
      status: 'Pending',
      priority: 'Normal',
    });
    setNewTaskTitle('');
  };

  const handleToggleDemoWorkflow = () => {
    if (demoMode) {
      stopDemoSession();
      return;
    }

    startDemoSession({
      fileTree: demoFileTree,
      logs: createDemoLogs(),
      nodes: demoNodes,
      edges: demoEdges,
      tasks: demoTasks,
    });

    setSelectedTask(demoTasks[0]);
  };

  return (
    <div className="w-full h-full bg-background border border-border rounded-lg p-6 overflow-y-auto flex flex-col">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-border shrink-0">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Settings2 className="w-6 h-6 text-primary" />
            Agent Orchestration
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            Track how software tasks move through PM, Developer, Reviewer, and QA agents via Band.
          </p>
        </div>

        <button
          onClick={handleToggleDemoWorkflow}
          className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors font-medium text-sm ${
            demoMode
              ? 'bg-secondary text-secondary-foreground border border-border hover:bg-secondary/80'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
          }`}
        >
          <Radio className="w-4 h-4" />
          {demoMode ? 'Exit Demo Workflow' : 'Run Demo Workflow'}
        </button>
      </div>

      {!demoMode && liveAgentCount === 0 && (
        <div className="flex-1 border border-dashed border-border rounded-lg bg-card p-12 text-center flex flex-col items-center justify-center">
          <Clock3 className="w-10 h-10 text-muted-foreground mb-3" />
          <h3 className="font-semibold text-foreground">No active workflow yet</h3>

        </div>
      )}

      {!demoMode && liveAgentCount > 0 && (
        <div className="flex-1 flex flex-col min-h-[500px]">
          <AgentNetworkGraph />
        </div>
      )}

      {demoMode && (
        <div className="flex flex-col gap-6">
          {/* Agent Topology Graph */}
          <div className="h-[400px] shrink-0">
            <AgentNetworkGraph />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_360px] gap-6">
          <section className="bg-card border border-border rounded-lg p-4 text-card-foreground">
            <div className="flex items-center gap-2 mb-4">
              <ClipboardList className="w-5 h-5 text-primary" />
              <h3 className="font-semibold text-foreground">Task Queue</h3>
            </div>

            <div className="space-y-3">
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                <SortableContext items={tasks.map(t => t.id)} strategy={verticalListSortingStrategy}>
                  {tasks.map((task) => (
                    <SortableTaskItem 
                      key={task.id} 
                      task={task} 
                      isSelected={selectedTask?.id === task.id} 
                      onClick={() => setSelectedTask(task)} 
                    />
                  ))}
                </SortableContext>
              </DndContext>
            </div>

            <form onSubmit={handleAddTask} className="mt-4 flex gap-2">
              <input 
                type="text" 
                placeholder="Quick add task..." 
                className="flex-1 bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground"
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
              />
              <button 
                type="submit"
                className="bg-primary text-primary-foreground p-2 rounded-md hover:bg-primary/90"
              >
                <PlusCircle className="w-5 h-5" />
              </button>
            </form>
          </section>

          <section className="bg-card border border-border rounded-lg p-5 text-card-foreground">
            <div className="mb-6">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Selected task
              </div>
              <h3 className="text-lg font-semibold text-foreground">{selectedTask.title}</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Current owner: {selectedTask.owner} · Status: {selectedTask.status}
              </p>
            </div>

            <div className="space-y-4">
              {selectedTask.journey.map((step, index) => {
                const Icon = step.icon;

                return (
                  <div key={`${selectedTask.id}-${step.agent}`} className="relative">
                    <div className="flex gap-4 p-4 border border-border rounded-lg bg-background">
                      <div className="w-11 h-11 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
                        <Icon className="w-5 h-5" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <h4 className="font-semibold text-sm text-foreground">{step.agent}</h4>
                            <p className="text-xs text-muted-foreground">{step.role}</p>
                          </div>

                          <span className="text-xs px-2 py-1 rounded-full bg-green-500/10 text-green-600 dark:text-green-400">
                            {step.status}
                          </span>
                        </div>

                        <p className="text-sm text-muted-foreground mt-3">{step.description}</p>
                        <p className="text-sm text-foreground mt-2">{step.output}</p>
                      </div>
                    </div>

                    {index < selectedTask.journey.length - 1 && (
                      <div className="flex justify-center py-2 text-muted-foreground">
                        <ArrowRight className="w-4 h-4 rotate-90" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          <section className="bg-card border border-border rounded-lg p-5 text-card-foreground">
            <div className="mb-5">
              <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                Band Context
              </div>
              <h3 className="font-semibold text-foreground">Latest handoff payload</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Structured context shared between agents through Band.
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 rounded-lg border border-border bg-background">
                <div className="text-xs text-muted-foreground mb-2">
                  {selectedTask.bandContext.from} → {selectedTask.bandContext.to}
                </div>
                <div className="font-medium text-sm text-foreground">
                  {selectedTask.bandContext.type}
                </div>

                <div className="mt-4 space-y-3 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground">Task brief</div>
                    <div className="text-foreground">{selectedTask.bandContext.brief}</div>
                  </div>

                  <div>
                    <div className="text-xs text-muted-foreground">Acceptance criteria</div>
                    <ul className="list-disc list-inside text-foreground mt-1 space-y-1">
                      {selectedTask.bandContext.criteria.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <div className="text-xs text-muted-foreground">Affected files</div>
                    <div className="mt-1 space-y-1 font-mono text-xs text-foreground">
                      {selectedTask.bandContext.files.map((file) => (
                        <div key={file}>{file}</div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-lg border border-dashed border-border bg-secondary/20">
                <div className="text-xs text-muted-foreground mb-2">Next expected handoff</div>
                <div className="text-sm font-medium text-foreground">
                  {selectedTask.bandContext.next}
                </div>
                <p className="text-sm text-muted-foreground mt-2">
                  {selectedTask.bandContext.nextPayload}
                </p>
              </div>
            </div>
          </section>
        </div>
        </div>
      )}
    </div>
  );
}