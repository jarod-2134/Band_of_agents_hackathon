import { useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useAgentStore } from '@/store/useAgentStore';

export function ASTGraph() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const currentOrgSlug = useAgentStore(state => state.currentOrgSlug);
  const currentRepoId = useAgentStore(state => state.currentRepoId);
  const [activeRepoDbId, setActiveRepoDbId] = useState('');

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
          const formattedData = {
            nodes: data.nodes.map((n: any) => ({ 
              id: n.id, 
              name: n.name, 
              val: n.node_type === 'file' ? 10 : 5, 
              group: n.node_type 
            })),
            links: data.edges.map((e: any) => ({ 
              source: e.source_id, 
              target: e.target_id, 
              name: e.relation_type 
            }))
          };
          setGraphData(formattedData);
        } else {
          setGraphData({ nodes: [], links: [] });
        }
      })
      .catch(err => console.error("Failed to load graph data:", err));
  }, [currentOrgSlug, currentRepoId]);

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
            graphData={graphData}
            nodeLabel="name"
            nodeAutoColorBy="group"
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            linkLabel="name"
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
