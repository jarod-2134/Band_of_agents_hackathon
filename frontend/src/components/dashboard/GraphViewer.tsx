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
  { id: 'planner', data: { label: 'Planner Agent' }, role: 'planner' },
  { id: 'engineer', data: { label: 'Engineer Agent' }, role: 'engineer' },
  { id: 'reviewer', data: { label: 'Reviewer Agent' }, role: 'reviewer' },
  { id: 'tester', data: { label: 'Tester Agent' }, role: 'tester' },
];

const demoEdges: GraphEdge[] = [
  { id: 'p-e', source: 'planner', target: 'engineer', animated: true },
  { id: 'e-r', source: 'engineer', target: 'reviewer', animated: true },
  { id: 'r-e', source: 'reviewer', target: 'engineer', animated: true },
  { id: 'r-p', source: 'reviewer', target: 'planner', animated: true },
  { id: 'p-t', source: 'planner', target: 'tester', animated: true },
  { id: 't-e', source: 'tester', target: 'engineer', animated: true },
  { id: 't-p', source: 'tester', target: 'planner', animated: true },
];

function createDemoLogs(): LogEntry[] {
  const base = Date.now();
  return [
    { id: 'd1', timestamp: base, type: 'action', agentRole: 'planner', message: 'Planner Agent invoked tool `create_task` for "Implement authentication framework".' },
    { id: 'd2', timestamp: base + 1000, type: 'action', agentRole: 'planner', message: 'Band handoff: Planner Agent dispatched execution payload to Engineer Agent.' },
    { id: 'd3', timestamp: base + 2000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent invoked tool `scaffold_template` to generate frontend/src/Login.tsx.' },
    { id: 'd4', timestamp: base + 3000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent invoked tool `run_terminal_command` (npm install jsonwebtoken).' },
    { id: 'd5', timestamp: base + 4000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent invoked tool `replace_file_content` to inject secure token validation.' },
    { id: 'd6', timestamp: base + 5000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent changed status to IDLE. Notifying Planner.' },
    { id: 'd7', timestamp: base + 6000, type: 'action', agentRole: 'planner', message: 'Planner Agent dispatched review payload to Reviewer Agent.' },
    { id: 'd8', timestamp: base + 7000, type: 'action', agentRole: 'reviewer', message: 'Reviewer Agent invoked tool `analyze_code_quality` (eslint frontend/src/Login.tsx).' },
    { id: 'd9', timestamp: base + 8000, type: 'action', agentRole: 'reviewer', message: 'Reviewer Agent invoked tool `leave_review_comment` (Missing error boundary on login form).' },
    { id: 'd10', timestamp: base + 9000, type: 'action', agentRole: 'reviewer', message: 'Reviewer Agent invoked tool `request_changes` routing task back to Engineer Agent.' },
    { id: 'd11', timestamp: base + 10000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent invoked tool `replace_file_content` to fix missing error boundary.' },
    { id: 'd12', timestamp: base + 11000, type: 'action', agentRole: 'reviewer', message: 'Reviewer Agent invoked tool `approve_branch`. Branch cleared for QA.' },
    { id: 'd13', timestamp: base + 12000, type: 'action', agentRole: 'planner', message: 'Planner Agent dispatched QA verification payload to Tester Agent.' },
    { id: 'd14', timestamp: base + 13000, type: 'action', agentRole: 'tester', message: 'Tester Agent invoked tool `generate_unit_test` scaffolding frontend/src/__tests__/LoginForm.test.tsx.' },
    { id: 'd15', timestamp: base + 14000, type: 'action', agentRole: 'tester', message: 'Tester Agent invoked tool `run_coverage_report` (pytest --cov/npm run test:cov).' },
    { id: 'd16', timestamp: base + 15000, type: 'action', agentRole: 'tester', message: 'Coverage drop detected! Tester Agent invoked tool `create_bug_report` and routed to Engineer.' },
    { id: 'd17', timestamp: base + 16000, type: 'action', agentRole: 'engineer', message: 'Engineer Agent fixed failing edge-case test.' },
    { id: 'd18', timestamp: base + 17000, type: 'action', agentRole: 'tester', message: 'Tester Agent verified 90%+ coverage. Invoked tool `report_test_results` (PASSED).' },
    { id: 'd19', timestamp: base + 18000, type: 'action', agentRole: 'planner', message: 'Planner Agent invoked tool `finalize_project`.' },
  ];
}

const demoTasks = [
  {
    id: 1,
    title: 'Implement Authentication Framework',
    owner: 'Planner Agent',
    status: 'Completed',
    priority: 'High',
    journey: [
      {
        agent: 'Planner Agent',
        role: 'Orchestration',
        status: 'Completed',
        icon: UserCog,
        description: 'Broke requirement into tickets and tracked DB task statuses.',
        output: 'Created DB Task #1 and delegated to Engineer via Band.',
      },
      {
        agent: 'Engineer Agent',
        role: 'Implementation',
        status: 'Completed',
        icon: Code,
        description: 'Scaffolded boilerplate, ran local terminal npm installs, and used token-optimized text replacement.',
        output: 'Built Login.tsx and auth.ts, ran local compilation sandbox.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Quality Gate',
        status: 'Completed',
        icon: SearchCheck,
        description: 'Ran `eslint` autonomously, logged feedback to DB, and forced an Engineer rework loop.',
        output: 'Approved branch after Engineer resolved the missing error boundary.',
      },
      {
        agent: 'Tester Agent',
        role: 'QA & Coverage',
        status: 'Completed',
        icon: ShieldCheck,
        description: 'Scaffolded tests using `generate_unit_test`, ran coverage, and filed an initial bug report before passing.',
        output: 'Reported PASSED milestone back to Planner.',
      },
    ],
    bandContext: {
      from: 'Tester Agent',
      to: 'Planner Agent',
      type: 'report_test_results',
      brief: 'Auth framework passed all unit tests and meets 90% coverage threshold.',
      criteria: ['Unit tests generated', 'Coverage > 80%', 'Bug reports resolved'],
      files: ['frontend/src/__tests__/LoginForm.test.tsx'],
      next: 'Planner Agent → finalize_project',
      nextPayload: 'Merge feature branch to main and complete milestone.',
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