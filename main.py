from graph import compiled_app
from langchain_core.messages import HumanMessage, BaseMessage

from state import AgentState
def run_app(user_input: str) -> AgentState:
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "retrieved_docs": [],
    }
    final_state = compiled_app.invoke(initial_state)
    return final_state

print(run_app("thời tiết hà nội ngay bây giờ")["final_response"].html)
