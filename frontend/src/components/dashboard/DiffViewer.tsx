import { DiffEditor } from '@monaco-editor/react';
import { useAgentStore } from '@/store/useAgentStore';
import { Code2 } from 'lucide-react';

type DiffData = {
  filePath: string;
  original: string;
  modified: string;
};

type DiffViewerProps = {
  diff: DiffData;
};

export function DiffViewer({ diff }: DiffViewerProps) {
  const theme = useAgentStore((state) => state.theme);
  const isDarkTheme = ['dark', 'cyberpunk', 'ocean'].includes(theme);

  const language = diff.filePath.endsWith('.py')
    ? 'python'
    : diff.filePath.endsWith('.md')
      ? 'markdown'
      : 'typescript';

  return (
    <div className="w-full h-full bg-card border border-border rounded-lg overflow-hidden flex flex-col shadow-sm">
      <div className="px-4 py-3 bg-secondary border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-primary/10 text-primary flex items-center justify-center">
            <Code2 className="w-5 h-5" />
          </div>

          <div>
            <div className="font-mono text-sm font-bold text-foreground">{diff.filePath}</div>
            <div className="text-xs text-muted-foreground">
              Modified by Developer Agent · ready for Reviewer Agent
            </div>
          </div>
        </div>

        <span className="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary font-medium">
          code diff
        </span>
      </div>

      <div className="flex-1 min-h-0">
        <DiffEditor
          key={`${diff.filePath}-${diff.original.length}-${diff.modified.length}`}
          height="100%"
          language={language}
          theme={isDarkTheme ? 'vs-dark' : 'light'}
          original={diff.original}
          modified={diff.modified}
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