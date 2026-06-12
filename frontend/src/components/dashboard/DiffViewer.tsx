import { DiffEditor } from '@monaco-editor/react';
import { useAgentStore } from '@/store/useAgentStore';

export function DiffViewer() {
  const currentDiff = useAgentStore((state) => state.currentDiff);

  if (!currentDiff) {
    return (
      <div className="w-full h-full bg-white border border-border rounded-lg flex items-center justify-center text-muted-foreground font-mono text-sm">
        Select a file or wait for agent modifications...
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-white border border-border rounded-lg overflow-hidden flex flex-col">
      <div className="px-4 py-2 bg-secondary border-b border-border text-sm font-mono flex items-center justify-between shrink-0">
        <span className="font-bold">{currentDiff.filePath}</span>
        <span className="text-muted-foreground text-xs">Reviewing changes</span>
      </div>
      <div className="flex-1 min-h-0">
        <DiffEditor
          height="100%"
          language="typescript" // Usually dynamic
          theme="light"
          original={currentDiff.original}
          modified={currentDiff.modified}
          options={{
            renderSideBySide: true,
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineHeight: 1.5,
          }}
        />
      </div>
    </div>
  );
}
