import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { CheckCircle2, Clock3, Loader2, GripVertical } from 'lucide-react';
import type { Task } from '@/store/useAgentStore';

interface SortableTaskItemProps {
  task: Task;
  isSelected: boolean;
  onClick: () => void;
}

export function SortableTaskItem({ task, isSelected, onClick }: SortableTaskItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`w-full flex items-center p-3 rounded-lg border transition-colors mb-3 ${
        isSelected ? 'border-primary bg-primary/10' : 'border-border bg-background hover:bg-secondary/50'
      }`}
    >
      <div 
        className="cursor-grab hover:text-primary active:cursor-grabbing p-1 mr-2 text-muted-foreground"
        {...attributes} 
        {...listeners}
      >
        <GripVertical className="w-4 h-4" />
      </div>

      <div className="flex-1 cursor-pointer text-left" onClick={onClick}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="font-medium text-sm text-foreground">{task.title}</div>
            <div className="text-xs text-muted-foreground mt-1">
              Owner: {task.owner}
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
            <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
          ) : (
            <Clock3 className="w-3.5 h-3.5" />
          )}
          <span>{task.status}</span>
          <span className="opacity-50">·</span>
          <span className="font-medium">{task.owner}</span>
        </div>
      </div>
    </div>
  );
}
