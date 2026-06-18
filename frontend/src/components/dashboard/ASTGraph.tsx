import { useEffect, useState, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { forceCollide } from 'd3-force';
import { useAgentStore } from '@/store/useAgentStore';

const useThemeColors = () => {
  const theme = useAgentStore(state => state.theme);
  const [colors, setColors] = useState({
    background: '#000000',
    foreground: '#ffffff',
    primary: '#3b82f6',
    primaryForeground: '#ffffff',
    secondary: '#1e293b',
    secondaryForeground: '#ffffff',
    accent: '#0ea5e9',
    accentForeground: '#ffffff',
    muted: '#475569'
  });

  useEffect(() => {
    // Small delay to ensure theme classes are applied to body
    const timeout = setTimeout(() => {
      const getVar = (name: string) => {
        const val = getComputedStyle(document.body).getPropertyValue(name).trim();
        return val;
      };
      
      setColors({
        background: getVar('--background') || '#000000',
        foreground: getVar('--foreground') || '#ffffff',
        primary: getVar('--primary') || '#3b82f6',
        primaryForeground: getVar('--primary-foreground') || '#ffffff',
        secondary: getVar('--secondary') || '#1e293b',
        secondaryForeground: getVar('--secondary-foreground') || '#ffffff',
        accent: getVar('--accent') || '#0ea5e9',
        accentForeground: getVar('--accent-foreground') || '#ffffff',
        muted: getVar('--muted-foreground') || '#475569'
      });
    }, 50);
    return () => clearTimeout(timeout);
  }, [theme]);

  return colors;
};

export function ASTGraph() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const currentOrgSlug = useAgentStore(state => state.currentOrgSlug);
  const currentRepoId = useAgentStore(state => state.currentRepoId);
  const [activeRepoDbId, setActiveRepoDbId] = useState('');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const colors = useThemeColors();
  const fgRef = useRef<any>();

  useEffect(() => {
    if (!currentOrgSlug || !currentRepoId) {
       setGraphData({ nodes: [], links: [] });
       setActiveRepoDbId('');
       return;
    }
    
    fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos`)
      .then(r => r.json())
      .then(data => {
        const repo = data.repositories?.find((r: any) => r.fs_path === currentRepoId);
        if (repo) {
          setActiveRepoDbId(repo.id);
          return fetch(`http://localhost:8000/orgs/${currentOrgSlug}/repos/${repo.id}/graph`);
        }
        return null;
      })
      .then(r => r ? r.json() : null)
      .then(data => {
        if (data && data.nodes) {
          // 1. Filter out imports, variables, and falsely indexed arrow function parameters
          const ignoredNames = new Set(['btn', 'doc', 'msg', 'cName', 'err', 'req', 'res', 'val', 'key']);
          const validNodes = data.nodes.filter((n: any) => 
            n.node_type !== 'variable' && 
            n.node_type !== 'import' && 
            !ignoredNames.has(n.name) &&
            !(n.node_type === 'function' && n.name.length <= 2)
          );
          const validNodeIds = new Set(validNodes.map((n: any) => n.id));
          
          // 2. Identify unique folders
          const folders = new Set<string>();
          validNodes.forEach((n: any) => {
            if (n.node_type === 'file') {
              const parts = n.name.split(/[/\\]/);
              if (parts.length > 1) {
                folders.add(parts.slice(0, -1).join('/'));
              } else {
                folders.add('root');
              }
            }
          });

          // 3. Format valid nodes
          const formattedNodes: any[] = validNodes.map((n: any) => {
            const parts = n.name.split(/[/\\]/);
            const isFile = n.node_type === 'file';
            const filename = parts[parts.length - 1];
            const folder = isFile ? (parts.length > 1 ? parts.slice(0, -1).join('/') : 'root') : null;
            
            return { 
              id: n.id, 
              name: filename, 
              fullName: n.name,
              folder: folder,
              val: isFile ? 8 : 4, // Files are medium, functions are small
              group: n.node_type 
            };
          });

          // 4. Inject Virtual Folder Nodes
          folders.forEach(folder => {
            formattedNodes.push({
              id: `folder_${folder}`,
              name: folder.split('/').pop() || folder,
              fullName: folder,
              folder: folder,
              val: 30, // Folders are massive
              group: 'folder'
            });
          });

          // 5. Filter valid links
          const formattedLinks = data.edges
            .filter((e: any) => validNodeIds.has(e.source_id) && validNodeIds.has(e.target_id))
            .map((e: any) => ({ 
              source: e.source_id, 
              target: e.target_id, 
              name: e.relation_type 
            }));

          // 6. Link files to their parent folders
          validNodes.forEach((n: any) => {
            if (n.node_type === 'file') {
              const parts = n.name.split(/[/\\]/);
              const folder = parts.length > 1 ? parts.slice(0, -1).join('/') : 'root';
              formattedLinks.push({
                source: `folder_${folder}`,
                target: n.id,
                name: 'contains'
              });
            }
          });

          setGraphData({ nodes: formattedNodes, links: formattedLinks });
        } else {
          setGraphData({ nodes: [], links: [] });
        }
      })
      .catch(err => console.error("Failed to load graph data:", err));
  }, [currentOrgSlug, currentRepoId]);

  useEffect(() => {
    if (fgRef.current) {
      // Repel nodes to prevent overlap, but keep them tighter than before
      fgRef.current.d3Force('charge').strength(-400);
      fgRef.current.d3Force('charge').distanceMax(400);
      // Make files closer to folders, and functions MUCH closer to files
      fgRef.current.d3Force('link').distance((link: any) => link.name === 'contains' ? 100 : 40);
      
      // Add collision force to spread nodes out circularly without overlapping
      fgRef.current.d3Force('collide', forceCollide().radius((node: any) => {
        const base = node.group === 'folder' ? 30 : (node.group === 'file' ? 20 : 10);
        return base;
      }).iterations(2));
    }
  }, [graphData]);

  // Generate a deterministic color based on a string (for folders)
  const stringToColor = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    return `hsl(${Math.abs(hash) % 360}, 75%, 40%)`;
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div className="p-4 border-b border-border bg-card shrink-0">
        <h2 className="text-lg font-semibold">AST Knowledge Graph</h2>
        <p className="text-sm text-muted-foreground">
          Topological mapping of the codebase for agents to traverse. {activeRepoDbId && `Repo ID: ${activeRepoDbId}`}
        </p>
      </div>
      <div className="flex-1 overflow-hidden bg-background">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            nodeLabel="fullName"
            nodeRelSize={8}
            linkColor={() => colors.muted}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel="name"
            backgroundColor="transparent"
            onNodeClick={(node) => {
              setSelectedNode(node);
            }}
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const label = node.name;
              
              // Scale fonts based on node importance. 
              // We use fixed sizes here so they scale up naturally when the user zooms in!
              let baseSize = 6;
              if (node.group === 'folder') baseSize = 20;
              else if (node.group === 'file') baseSize = 14;
              else baseSize = 6; // functions, classes

              // Ensure text remains readable when zoomed far out
              const minSize = (node.group === 'folder' ? 5 : 2) / globalScale;
              const fontSize = Math.max(baseSize, minSize);
              
              ctx.font = `600 ${fontSize}px Sans-Serif`;
              const textWidth = ctx.measureText(label).width;
              const padding = fontSize * (node.group === 'folder' ? 1.2 : 0.8);
              const bckgDimensions = [textWidth + padding, fontSize + padding];

              // Determine color based on node group and folder
              let nodeColor = colors.secondary;
              let textColor = colors.secondaryForeground;
              let strokeColor = node.id === selectedNode?.id ? colors.primary : colors.muted;
              let lineWidth = (node.id === selectedNode?.id ? 3 : 1) / globalScale;

              if (node.group === 'folder') {
                nodeColor = stringToColor(node.folder || '');
                textColor = '#ffffff';
                strokeColor = node.id === selectedNode?.id ? colors.primary : '#ffffff';
                lineWidth = (node.id === selectedNode?.id ? 5 : 2) / globalScale;
              } else if (node.group === 'file') {
                nodeColor = colors.background;
                strokeColor = node.id === selectedNode?.id ? colors.primary : stringToColor(node.folder || '');
                textColor = colors.foreground;
                lineWidth = (node.id === selectedNode?.id ? 4 : 1.5) / globalScale;
              } else if (node.group === 'class') {
                nodeColor = colors.accent;
                textColor = colors.accentForeground;
              }

              // Draw rounded rectangle background
              ctx.fillStyle = nodeColor;
              ctx.beginPath();
              const x = node.x - bckgDimensions[0] / 2;
              const y = node.y - bckgDimensions[1] / 2;
              const w = bckgDimensions[0];
              const h = bckgDimensions[1];
              const r = fontSize * 0.3; // border radius
              ctx.moveTo(x + r, y);
              ctx.lineTo(x + w - r, y);
              ctx.quadraticCurveTo(x + w, y, x + w, y + r);
              ctx.lineTo(x + w, y + h - r);
              ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
              ctx.lineTo(x + r, y + h);
              ctx.quadraticCurveTo(x, y + h, x, y + h - r);
              ctx.lineTo(x, y + r);
              ctx.quadraticCurveTo(x, y, x + r, y);
              ctx.closePath();
              ctx.fill();
              
              // Add a subtle border
              ctx.strokeStyle = strokeColor;
              ctx.lineWidth = lineWidth;
              ctx.stroke();

              // Draw text
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = textColor;
              ctx.fillText(label, node.x, node.y);

              node.__bckgDimensions = bckgDimensions;
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            {activeRepoDbId ? "Loading graph data or no AST data available..." : "No graph data available. Select a repository first."}
          </div>
        )}
      </div>
    </div>
  );
}
