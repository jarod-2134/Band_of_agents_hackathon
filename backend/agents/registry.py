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

    def get_graph(self):
        nodes = []
        edges = []
        
        for agent in self.agents.values():
            color = "#000"
            if agent.role == "ceo": color = "hsl(0, 100%, 50%)" # Red
            elif agent.role == "manager": color = "hsl(280, 100%, 50%)" # Purple
            elif agent.role == "engineer": color = "hsl(120, 100%, 30%)" # Green
            elif agent.role == "reviewer": color = "hsl(200, 100%, 40%)" # Blue
            elif agent.role == "tester": color = "hsl(30, 100%, 50%)" # Orange

            nodes.append({
                "id": agent.id,
                "data": { "label": agent.name },
                "style": { "border": f"2px solid {color}", "background": "#fff", "color": "#000", "fontWeight": "bold" },
                "role": agent.role
            })

            if agent.parent_id:
                edges.append({
                    "id": f"e-{agent.parent_id}-{agent.id}",
                    "source": agent.parent_id,
                    "target": agent.id,
                    "animated": True,
                    "style": { "stroke": "#000" }
                })

        return {"nodes": nodes, "edges": edges}

registry = AgentRegistry()
