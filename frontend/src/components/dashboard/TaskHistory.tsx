import { Filter, Search, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

const mockTasks = [
  { id: 'tsk-001', name: 'Refactor Authentication Module', role: 'Engineer', status: 'completed', time: '14m 23s', date: '2 hours ago' },
  { id: 'tsk-002', name: 'Review PR #44', role: 'Reviewer', status: 'completed', time: '2m 10s', date: '5 hours ago' },
  { id: 'tsk-003', name: 'Generate UI tests for Dashboard', role: 'Engineer', status: 'failed', time: '8m 45s', date: 'Yesterday' },
  { id: 'tsk-004', name: 'Plan Q3 Feature Sprint', role: 'Manager', status: 'completed', time: '45m 12s', date: 'Yesterday' },
  { id: 'tsk-005', name: 'Optimize Database Queries', role: 'Engineer', status: 'running', time: '12m 00s', date: 'Just now' },
];

export function TaskHistory() {
  return (
    <div className="flex-1 overflow-y-auto p-8 bg-white h-full">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-8 border-b pb-4">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Task History</h1>
            <p className="text-neutral-500 mt-1">Review past and currently active agent tasks.</p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input 
                type="text" 
                placeholder="Search tasks..." 
                className="pl-9 pr-4 py-2 border rounded-md text-sm outline-none focus:ring-2 focus:ring-indigo-500 w-64"
              />
            </div>
            <button className="flex items-center gap-2 px-3 py-2 border rounded-md text-sm font-medium hover:bg-neutral-50 text-neutral-700">
              <Filter className="w-4 h-4" /> Filter
            </button>
          </div>
        </div>

        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-50 border-b">
              <tr>
                <th className="px-6 py-4 font-semibold text-neutral-600">Task Name</th>
                <th className="px-6 py-4 font-semibold text-neutral-600">Agent Role</th>
                <th className="px-6 py-4 font-semibold text-neutral-600">Status</th>
                <th className="px-6 py-4 font-semibold text-neutral-600">Duration</th>
                <th className="px-6 py-4 font-semibold text-neutral-600 text-right">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {mockTasks.map((task) => (
                <tr key={task.id} className="hover:bg-neutral-50/50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-neutral-900">{task.name}</div>
                    <div className="text-xs text-neutral-500 font-mono mt-0.5">{task.id}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                      task.role === 'Manager' ? 'bg-indigo-100 text-indigo-700' :
                      task.role === 'Engineer' ? 'bg-blue-100 text-blue-700' :
                      'bg-emerald-100 text-emerald-700'
                    }`}>
                      {task.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {task.status === 'completed' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                      {task.status === 'failed' && <XCircle className="w-4 h-4 text-red-500" />}
                      {task.status === 'running' && <Loader2 className="w-4 h-4 text-indigo-500 animate-spin" />}
                      <span className={`capitalize font-medium ${
                        task.status === 'completed' ? 'text-green-700' :
                        task.status === 'failed' ? 'text-red-700' :
                        'text-indigo-700'
                      }`}>
                        {task.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-neutral-600">{task.time}</td>
                  <td className="px-6 py-4 text-right text-neutral-500">{task.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="mt-4 flex items-center justify-between text-sm text-neutral-500">
          <div>Showing 5 of 1,284 tasks</div>
          <div className="flex items-center gap-2">
            <button className="px-3 py-1 border rounded hover:bg-neutral-50 disabled:opacity-50">Previous</button>
            <button className="px-3 py-1 border rounded hover:bg-neutral-50">Next</button>
          </div>
        </div>

      </div>
    </div>
  );
}
