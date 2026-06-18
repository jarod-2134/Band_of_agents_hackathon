import { useCallback, useEffect, useState, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import { useAgentStore, type GraphNode, type GraphEdge } from '@/store/useAgentStore';
import { Activity, Clock3, MessageSquareText, ShieldAlert, FileCode2 } from 'lucide-react';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

const nodeWidth = 220;
const nodeHeight = 80;

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'TB') => {
  dagreGraph.setGraph({ rankdir: direction });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const newNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const newNode = {
      ...node,
      targetPosition: 'top',
      sourcePosition: 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
    return newNode;
  });

  return { nodes: newNodes, edges };
};

const CustomNode = ({ data }: any) => {
  return (
    <div
      className="px-4 py-3 shadow-md rounded-md bg-card border-2 flex flex-col items-center justify-center relative min-w-[200px]"
      style={{ borderColor: data.color || '#64748b' }}
      onMouseEnter={data.onHover}
      onMouseLeave={data.onLeave}
      onClick={data.onClick}
    >
      <Handle type="target" position={Position.Top} className="w-16 !bg-muted-foreground" />
      <div className="font-bold text-sm text-foreground">{data.label}</div>
      {data.role && (
        <div className="text-xs text-muted-foreground mt-1 px-2 py-0.5 bg-secondary rounded-full uppercase tracking-wider">
          {data.role.replace(/_/g, ' ')}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="w-16 !bg-muted-foreground" />
    </div>
  );
};

const nodeTypes = { custom: CustomNode };

export function AgentNetworkGraph() {
  const storeNodes = useAgentStore((state) => state.nodes);
  const storeEdges = useAgentStore((state) => state.edges);
  const logs = useAgentStore((state) => state.logs);
  
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Convert store nodes/edges to React Flow format
  useEffect(() => {
    if (!storeNodes || storeNodes.length === 0) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const flowNodes = storeNodes.map((n: GraphNode) => {
      // Extract color from style if it exists
      const color = n.style?.border?.match(/hsl\([^)]+\)|#[0-9a-fA-F]+/)?.[0] || '#64748b';
      
      return {
        id: n.id,
        type: 'custom',
        position: { x: 0, y: 0 },
        data: {
          label: n.data.label,
          role: n.role,
          color,
          onHover: () => setHoveredNodeId(n.id),
          onLeave: () => setHoveredNodeId(null),
          onClick: () => setSelectedNodeId(n.id),
        },
      };
    });

    const flowEdges = storeEdges.map((e: GraphEdge) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      animated: e.animated,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#64748b' },
      style: { stroke: '#64748b', strokeWidth: 2 },
    }));

    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(flowNodes, flowEdges);
    setNodes(layoutedNodes);
    setEdges(layoutedEdges);
  }, [storeNodes, storeEdges, setNodes, setEdges]);

  // Derived data for tooltip and side panel
  const getLogsForNode = useCallback((nodeId: string) => {
    const node = storeNodes.find(n => n.id === nodeId);
    if (!node) return [];
    // Match by agentRole if possible (simplification since backend sets role)
    return logs.filter(l => l.agentRole === node.role).reverse();
  }, [storeNodes, logs]);

  const hoveredLogs = hoveredNodeId ? getLogsForNode(hoveredNodeId) : [];
  const latestHoverLog = hoveredLogs.length > 0 ? hoveredLogs[0] : null;

  const selectedLogs = selectedNodeId ? getLogsForNode(selectedNodeId) : [];
  const selectedNode = storeNodes.find(n => n.id === selectedNodeId);

  const touchedFiles = useMemo(() => {
    if (!selectedLogs.length) return [];
    const files = new Set<string>();
    // Regex for basic file paths or names (e.g., Login.tsx, src/auth.ts)
    const fileRegex = /([a-zA-Z0-9_\-\/]+\.(tsx|ts|py|js|jsx|css|html|md|json|yml|yaml))/g;
    selectedLogs.forEach(log => {
      const matches = log.message.match(fileRegex);
      if (matches) {
        matches.forEach(m => {
          // Exclude any trailing punctuation that might get caught
          files.add(m.replace(/[.,:;)]+$/, ''));
        });
      }
    });
    return Array.from(files);
  }, [selectedLogs]);

  return (
    <div className="relative w-full h-full flex bg-background/50 border border-border rounded-lg overflow-hidden">
      <div className="flex-1 h-full relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-right"
        >
          <Background color="#ccc" gap={16} />
          <Controls />
        </ReactFlow>

        {/* Hover Tooltip */}
        {hoveredNodeId && !selectedNodeId && latestHoverLog && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 bg-card border border-border shadow-lg rounded-lg p-3 w-80 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-2 mb-1">
              <MessageSquareText className="w-4 h-4 text-primary" />
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Latest Activity</span>
            </div>
            <p className="text-sm text-foreground line-clamp-3">{latestHoverLog.message}</p>
            <div className="text-[10px] text-muted-foreground mt-2 text-right">
              {new Date(latestHoverLog.timestamp).toLocaleTimeString()}
            </div>
          </div>
        )}
      </div>

      {/* Selected Node Side Panel */}
      {selectedNodeId && selectedNode && (
        <div className="w-80 h-full border-l border-border bg-card shadow-xl flex flex-col animate-in slide-in-from-right-8 duration-300">
          <div className="p-4 border-b border-border flex items-center justify-between bg-secondary/30">
            <div>
              <h3 className="font-bold text-lg text-foreground">{selectedNode.data.label}</h3>
              <p className="text-xs text-muted-foreground uppercase">{selectedNode.role}</p>
            </div>
            <button 
              onClick={() => setSelectedNodeId(null)}
              className="text-muted-foreground hover:text-foreground text-xl font-bold px-2"
            >
              &times;
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            
            {touchedFiles.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-3">
                  <FileCode2 className="w-4 h-4" /> Touched Files
                </h4>
                <div className="flex flex-wrap gap-2">
                  {touchedFiles.map(file => (
                    <span key={file} className="text-xs font-mono bg-secondary text-secondary-foreground px-2 py-1 rounded-md border border-border">
                      {file}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2 mb-4">
                <Activity className="w-4 h-4" /> Activity History
              </h4>
            
            {selectedLogs.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                No activity logs yet.
              </div>
            ) : (
              <div className="space-y-4">
                {selectedLogs.map(log => (
                  <div key={log.id} className="relative pl-4 border-l-2 border-border/50">
                    <div className="absolute -left-[5px] top-1 w-2 h-2 rounded-full bg-primary" />
                    <div className="flex items-center gap-2 mb-1">
                      {log.type === 'error' && <ShieldAlert className="w-3.5 h-3.5 text-destructive" />}
                      {log.type === 'action' && <Activity className="w-3.5 h-3.5 text-green-500" />}
                      <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                        <Clock3 className="w-3 h-3" />
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className={`text-sm ${log.type === 'error' ? 'text-destructive' : 'text-foreground'}`}>
                      {log.message}
                    </p>
                  </div>
                ))}
              </div>
            )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
