class AgentRegistry:
    def __init__(self):
        # Maps org_slug -> {agent_id: agent}
        self._org_agents = {}
        self.on_graph_update = None

    def register(self, org_slug, agent):
        if org_slug not in self._org_agents:
            self._org_agents[org_slug] = {}
        self._org_agents[org_slug][agent.id] = agent
        if self.on_graph_update:
            self.on_graph_update(org_slug)

    def unregister(self, org_slug, agent_id):
        if org_slug in self._org_agents and agent_id in self._org_agents[org_slug]:
            del self._org_agents[org_slug][agent_id]
            if self.on_graph_update:
                self.on_graph_update(org_slug)

    def get_agent(self, org_slug, agent_id):
        return self._org_agents.get(org_slug, {}).get(agent_id)

    def get_all_agents(self, org_slug):
        return list(self._org_agents.get(org_slug, {}).values())

    def clear_org(self, org_slug):
        if org_slug in self._org_agents:
            del self._org_agents[org_slug]
            if self.on_graph_update:
                self.on_graph_update(org_slug)

    def find_subsidiary_by_role(self, org_slug: str, parent_id: str, role: str):
        for agent in self._org_agents.get(org_slug, {}).values():
            if getattr(agent, 'parent_id', None) == parent_id and agent.role == role:
                return agent
        return None

    def get_graph(self, org_slug: str):
        """
        Generates nodes and directional edges representing the active cluster topology for a specific org.
        """
        nodes = []
        edges = []
        
        agents = self._org_agents.get(org_slug, {})
        for agent in agents.values():
            # Default fallback border configuration color
            color = "#64748b" # Slate
            
            # 1. Leadership & Orchestration Core
            if agent.role == "ceo": 
                color = "hsl(0, 100%, 50%)"       # Bright Red
            elif agent.role == "product_manager": 
                color = "hsl(340, 85%, 45%)"     # Crimson/Rose
            elif agent.role == "scrum_master": 
                color = "hsl(280, 100%, 50%)"    # Vivid Purple
            elif agent.role == "architect": 
                color = "hsl(240, 100%, 60%)"    # Royal Blue
                
            # 2. Specialized Engineering Core (Green Spectrum)
            elif agent.role == "backend_engineer": 
                color = "hsl(120, 100%, 30%)"    # Forest Green
            elif agent.role == "frontend_engineer": 
                color = "hsl(145, 80%, 40%)"     # Emerald Mint
            elif agent.role == "data_engineer": 
                color = "hsl(165, 100%, 35%)"    # Deep Teal
                
            # 3. Quality Assurance & Evaluation Gates (Orange / Gold Spectrum)
            elif agent.role == "security_auditor": 
                color = "hsl(15, 100%, 50%)"     # Red-Orange
            elif agent.role == "peer_review_reviewer": 
                color = "hsl(35, 100%, 45%)"     # Amber/Gold
            elif agent.role == "automation_tester": 
                color = "hsl(48, 100%, 45%)"     # Pure Orange
                
            # 4. Infrastructure & Platform Core (Cyan Spectrum)
            elif agent.role == "infrastructure_engineer": 
                color = "hsl(195, 100%, 40%)"    # Cyan/Sky
            elif agent.role == "release_manager": 
                color = "hsl(215, 90%, 50%)"     # Electric Denim

            nodes.append({
                "id": agent.id,
                "data": { "label": agent.name },
                "style": { 
                    "border": f"2px solid {color}", 
                    "background": "#fff", 
                    "color": "#000", 
                    "fontWeight": "bold",
                    "borderRadius": "6px",
                    "padding": "10px"
                },
                "role": agent.role
            })

            if agent.parent_id:
                edges.append({
                    "id": f"e-{agent.parent_id}-{agent.id}",
                    "source": agent.parent_id,
                    "target": agent.id,
                    "animated": True,
                    "style": { "stroke": "#475569", "strokeWidth": 2 }
                })

        return {"nodes": nodes, "edges": edges}

registry = AgentRegistry()