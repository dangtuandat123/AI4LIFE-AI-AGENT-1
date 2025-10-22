from langgraph.graph import END, StateGraph

from agents import (
    checkbudget_agent,
    final_agent,
    node_get_schema,
    planner_agent,
    query_agent,
    router_agent,
)
from state import AgentState


def route_by_router_response(state: AgentState) -> str:
    """Return the next agent id chosen by the router agent."""
    decision = state["route_response"].next_agent
    print(
        "Condition Check - Route Decision:"
        f" {state['route_response'].reason}, Next Agent: {decision}"
    )
    return decision


def build_graph() -> StateGraph[AgentState]:
   
    workflow = StateGraph(AgentState)
    

    workflow.add_node("final_agent", final_agent)
    workflow.add_node("router_agent", router_agent)
    workflow.add_node("planner_agent", planner_agent)
    workflow.add_node("query_agent", query_agent)
    workflow.add_node("checkbudget_agent", checkbudget_agent)
    workflow.add_node("node_get_schema", node_get_schema)
    
    workflow.set_entry_point("node_get_schema")
    
    workflow.add_edge("node_get_schema", "router_agent")
    workflow.add_edge("planner_agent", "query_agent")
    workflow.add_edge("query_agent", "router_agent")
    workflow.add_edge("checkbudget_agent", "router_agent")

    workflow.add_conditional_edges(
        "router_agent",
        route_by_router_response,
        {
            "planner_agent": "planner_agent",
            "query_agent": "query_agent",
            "checkbudget_agent": "checkbudget_agent",
            "final_agent": "final_agent",
        },
    )
    
    workflow.add_edge("final_agent", END)
    
    app = workflow.compile()
    
    return app

compiled_app = build_graph()

if __name__ == "__main__":
    with open("workflow.png", "wb") as f:
        f.write(compiled_app.get_graph().draw_mermaid_png())
