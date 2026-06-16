class AgentRegistry:
    def __init__(self):
        self.agents = {}
        self.on_graph_update = None

    def register(self, agent):
        self.agents[agent.id] = agent
        if self.on_graph_update:
            self.on_graph_update()

    def unregister(self, agent_id):
        if agent_id in self.agents:
            del self.agents[agent_id]
            if self.on_graph_update:
                self.on_graph_update()

    def get_agent(self, agent_id):
        return self.agents.get(agent_id)

    def find_subsidiary_by_role(self, parent_id: str, role: str):
        for agent in self.agents.values():
            if getattr(agent, 'parent_id', None) == parent_id and agent.role == role:
                return agent
        return None

    def get_graph(self):
        """
        Generates nodes and directional edges representing the active cluster topology.
        Maps unique HSL color palettes to the newly expanded 12-role engine profiles.
        """
        nodes = []
        edges = []
        
        for agent in self.agents.values():
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