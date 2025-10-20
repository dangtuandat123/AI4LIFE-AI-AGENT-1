from langgraph.graph import StateGraph, END
from state import AgentState
from agents import planner_agent, code_agent, final_agent, router_agent
from IPython.display import Image, display

def condition_for_code_agent(state: AgentState) -> bool:
    print(f"Condition Check - Route Decision:{state['route_response'].reason}, Next Agent: {state['route_response'].next_agent}")
    return state["route_response"].next_agent


def build_graph() -> StateGraph[AgentState]:
   
    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner_agent", planner_agent)
    workflow.add_node("code_agent", code_agent)
    workflow.add_node("final_agent", final_agent)
    workflow.add_node("router_agent", router_agent)
    
    workflow.set_entry_point("planner_agent")
    
    workflow.add_edge("planner_agent", "router_agent")
    workflow.add_edge("code_agent", "router_agent")

    workflow.add_conditional_edges(
        "router_agent", 
        condition_for_code_agent,
        {
            "code_agent": "code_agent",
            "final_agent": "final_agent"
        }
    )
    
    workflow.add_edge("final_agent", END)
    
    app = workflow.compile()
    
    return app

compiled_app = build_graph()

if __name__ == "__main__":
    with open("workflow.png", "wb") as f:
        f.write(compiled_app.get_graph().draw_mermaid_png())