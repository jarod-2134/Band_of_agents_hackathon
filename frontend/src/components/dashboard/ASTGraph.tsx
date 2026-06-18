import { useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export function ASTGraph() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [repoId, setRepoId] = useState('');

  useEffect(() => {
    // Fetch the first available repo in the test organization
    fetch('http://localhost:8000/orgs/jarod-2134/repos')
      .then(r => r.json())
      .then(data => {
        if (data.repositories && data.repositories.length > 0) {
          const id = data.repositories[0].id;
          setRepoId(id);
          return fetch(`http://localhost:8000/orgs/jarod-2134/repos/${id}/graph`);
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
        }
      })
      .catch(err => console.error("Failed to load graph data:", err));
  }, []);

  return (
    <div className="w-full h-full flex flex-col">
      <div className="p-4 border-b border-border bg-card shrink-0">
        <h2 className="text-lg font-semibold">AST Knowledge Graph</h2>
        <p className="text-sm text-muted-foreground">
          Topological mapping of the codebase for agents to traverse. {repoId && `Repo: ${repoId}`}
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
            {repoId ? "Loading graph data or no AST data available..." : "No graph data available. Clone a repository first."}
          </div>
        )}
      </div>
    </div>
  );
}
