import { useState } from 'react';
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
  AlertCircle,
} from 'lucide-react';

const tasks = [
  {
    id: 1,
    title: 'Build login page',
    owner: 'Developer Agent',
    status: 'In progress',
    priority: 'High',
    journey: [
      {
        agent: 'PM Agent',
        role: 'Planning',
        status: 'Completed',
        icon: UserCog,
        description: 'Broke the user request into implementation steps and acceptance criteria.',
        output: 'Created task brief, priority, expected files, and handoff payload.',
      },
      {
        agent: 'Developer Agent',
        role: 'Implementation',
        status: 'Working',
        icon: Code,
        description: 'Implementing the login UI, form validation, and submit state.',
        output: 'Currently editing Login.tsx and auth.ts.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Review',
        status: 'Waiting',
        icon: SearchCheck,
        description: 'Will review code quality, edge cases, and possible auth risks.',
        output: 'Waiting for developer handoff.',
      },
      {
        agent: 'QA Agent',
        role: 'Testing',
        status: 'Waiting',
        icon: ShieldCheck,
        description: 'Will verify expected behavior and test coverage.',
        output: 'Waiting for review approval.',
      },
    ],
    bandContext: {
      from: 'PM Agent',
      to: 'Developer Agent',
      type: 'implementation_task',
      brief: 'Build a login page with form validation.',
      criteria: ['Email input', 'Password input', 'Validation errors', 'Loading state on submit'],
      files: ['frontend/src/Login.tsx', 'frontend/src/auth.ts'],
      next: 'Developer Agent → Reviewer Agent',
      nextPayload: 'Code summary, changed files, known risks, and review request.',
    },
  },
  {
    id: 2,
    title: 'Review authentication flow',
    owner: 'Reviewer Agent',
    status: 'In review',
    priority: 'Medium',
    journey: [
      {
        agent: 'PM Agent',
        role: 'Planning',
        status: 'Completed',
        icon: UserCog,
        description: 'Assigned the authentication flow to review after implementation.',
        output: 'Defined review scope: login, token handling, and error states.',
      },
      {
        agent: 'Developer Agent',
        role: 'Implementation',
        status: 'Completed',
        icon: Code,
        description: 'Submitted the authentication flow for review.',
        output: 'Changed auth.ts, Login.tsx, and session.ts.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Review',
        status: 'Working',
        icon: SearchCheck,
        description: 'Checking security edge cases and failure behavior.',
        output: 'Reviewing token refresh logic and invalid password handling.',
      },
      {
        agent: 'QA Agent',
        role: 'Testing',
        status: 'Waiting',
        icon: ShieldCheck,
        description: 'Will test the flow after review approval.',
        output: 'Waiting for reviewer decision.',
      },
    ],
    bandContext: {
      from: 'Developer Agent',
      to: 'Reviewer Agent',
      type: 'review_request',
      brief: 'Review the authentication flow before QA testing.',
      criteria: ['Token handling is safe', 'Errors are visible to users', 'No sensitive data in logs'],
      files: ['frontend/src/auth.ts', 'frontend/src/session.ts', 'frontend/src/Login.tsx'],
      next: 'Reviewer Agent → QA Agent',
      nextPayload: 'Review decision, risks found, and suggested QA test cases.',
    },
  },
  {
    id: 3,
    title: 'Write dashboard tests',
    owner: 'QA Agent',
    status: 'Waiting',
    priority: 'Medium',
    journey: [
      {
        agent: 'PM Agent',
        role: 'Planning',
        status: 'Completed',
        icon: UserCog,
        description: 'Requested regression tests for the dashboard workflow.',
        output: 'Created test scope for task queue, journey view, and Band context panel.',
      },
      {
        agent: 'Developer Agent',
        role: 'Implementation',
        status: 'Completed',
        icon: Code,
        description: 'Prepared testable dashboard components.',
        output: 'Exposed stable labels and component structure for QA.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Review',
        status: 'Completed',
        icon: SearchCheck,
        description: 'Confirmed the dashboard is ready for UI tests.',
        output: 'Approved test target list.',
      },
      {
        agent: 'QA Agent',
        role: 'Testing',
        status: 'Waiting',
        icon: ShieldCheck,
        description: 'Will write and run tests for the dashboard workflow.',
        output: 'Waiting for test environment availability.',
      },
    ],
    bandContext: {
      from: 'Reviewer Agent',
      to: 'QA Agent',
      type: 'qa_handoff',
      brief: 'Create dashboard tests for the agent workflow UI.',
      criteria: ['Task selection updates details', 'Journey matches selected task', 'Band payload changes per task'],
      files: ['frontend/src/components/dashboard/GraphViewer.tsx'],
      next: 'QA Agent → PM Agent',
      nextPayload: 'Test results, failed cases, and completion status.',
    },
  },
  {
    id: 4,
    title: 'Prepare release notes',
    owner: 'PM Agent',
    status: 'Completed',
    priority: 'Low',
    journey: [
      {
        agent: 'PM Agent',
        role: 'Planning',
        status: 'Completed',
        icon: UserCog,
        description: 'Summarized completed work into release notes.',
        output: 'Prepared user-facing summary for the demo release.',
      },
      {
        agent: 'Developer Agent',
        role: 'Implementation',
        status: 'Completed',
        icon: Code,
        description: 'Confirmed changed files and implementation scope.',
        output: 'Provided list of modified dashboard components.',
      },
      {
        agent: 'Reviewer Agent',
        role: 'Code Review',
        status: 'Completed',
        icon: SearchCheck,
        description: 'Checked that release notes match actual changes.',
        output: 'Approved release notes for presentation.',
      },
      {
        agent: 'QA Agent',
        role: 'Testing',
        status: 'Completed',
        icon: ShieldCheck,
        description: 'Confirmed demo scenario is ready.',
        output: 'Marked task as completed.',
      },
    ],
    bandContext: {
      from: 'QA Agent',
      to: 'PM Agent',
      type: 'completion_report',
      brief: 'Release notes are ready for the final demo.',
      criteria: ['Workflow described clearly', 'Changed files included', 'Demo value explained'],
      files: ['README.md', 'frontend/src/components/dashboard/GraphViewer.tsx'],
      next: 'PM Agent → Done',
      nextPayload: 'Final task closure and demo summary.',
    },
  },
];

export function GraphViewer() {
  const [selectedTask, setSelectedTask] = useState(tasks[0]);

  const hasJourney = selectedTask.journey && selectedTask.journey.length > 0;
  const hasBandContext = Boolean(selectedTask.bandContext);

  return (
    <div className="w-full h-full bg-background border border-border rounded-lg p-6 overflow-y-auto">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-border">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Settings2 className="w-6 h-6 text-primary" />
            Agent Orchestration
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            Track how software tasks move through PM, Developer, Reviewer, and QA agents via Band.
          </p>
        </div>

        <button className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90 transition-colors font-medium text-sm">
          <Radio className="w-4 h-4" />
          Run Demo Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_360px] gap-6">
        <section className="bg-card border border-border rounded-lg p-4 text-card-foreground">
          <div className="flex items-center gap-2 mb-4">
            <ClipboardList className="w-5 h-5 text-primary" />
            <h3 className="font-semibold text-foreground">Task Queue</h3>
          </div>

          <div className="space-y-3">
            {tasks.map((task) => (
              <button
                key={task.id}
                onClick={() => setSelectedTask(task)}
                className={`w-full text-left p-4 rounded-lg border transition-colors ${
                  selectedTask.id === task.id
                    ? 'border-primary bg-primary/10'
                    : 'border-border bg-background hover:bg-secondary/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-sm text-foreground">{task.title}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Current owner: {task.owner}
                    </div>
                  </div>
                  <span className="text-[11px] px-2 py-1 rounded-full bg-secondary text-secondary-foreground">
                    {task.priority}
                  </span>
                </div>

                <div className="flex items-center gap-2 mt-3 text-xs text-muted-foreground">
                  {task.status === 'Completed' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                  ) : task.status === 'In progress' || task.status === 'In review' ? (
                    <Loader2 className="w-3.5 h-3.5 text-primary" />
                  ) : (
                    <Clock3 className="w-3.5 h-3.5" />
                  )}
                  {task.status}
                </div>
              </button>
            ))}
          </div>
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

          {!hasJourney && (
            <div className="border border-dashed border-border rounded-lg p-8 text-center text-muted-foreground">
              <AlertCircle className="w-8 h-8 mx-auto mb-3 opacity-60" />
              <div className="font-medium text-foreground">No workflow available yet</div>
              <p className="text-sm mt-1">
                This task has not received agent handoffs through Band.
              </p>
            </div>
          )}

          {hasJourney && (
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

                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              step.status === 'Completed'
                                ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                                : step.status === 'Working'
                                  ? 'bg-primary/10 text-primary'
                                  : 'bg-secondary text-secondary-foreground'
                            }`}
                          >
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
          )}
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

          {!hasBandContext && (
            <div className="border border-dashed border-border rounded-lg p-8 text-center text-muted-foreground">
              <AlertCircle className="w-8 h-8 mx-auto mb-3 opacity-60" />
              <div className="font-medium text-foreground">No Band payload yet</div>
              <p className="text-sm mt-1">No structured handoff has been recorded for this task.</p>
            </div>
          )}

          {hasBandContext && (
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
          )}
        </section>
      </div>
    </div>
  );
}