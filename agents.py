from utils import (
    get_embedding_model, 
    create_agent_basic, 
    create_agent_react, 
    print_colored,
    invoke_with_retry
)
from state import (
    AgentState,
    FinalResponse,
    RouterResponse
)
from prompts import (
    SYSTEM_PROMPT_ROUTER_AGENT,
    SYSTEM_PROMPT_PLANNER_AGENT,
    SYSTEM_PROMPT_FINAL_AGENT,
    SYSTEM_PROMPT_CODE_AGENT,
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tools import search_web



# start agent
def planner_agent(state: AgentState) -> AgentState:
    print_colored("Planner Agent Invoked", "green")
    llm = create_agent_basic()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_PLANNER_AGENT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    chain = prompt | llm
    response = invoke_with_retry(
        chain,
        {"messages": state["messages"]},
        state,
        "Planner Agent",
    )
    state["messages"].append(response)
    state["agent_response"] = response.content
    state["planner_response"] = response.content
    state["agent_last"] = "planner_agent"
    print_colored(f"Planner Agent Response:\n {response.content}", "yellow")
    return state


def code_agent(state: AgentState) -> AgentState:
    print_colored("Code Agent Invoked", "green")
    agent = create_agent_react(
        tools=[search_web],
        system_prompt=SYSTEM_PROMPT_CODE_AGENT,
    )
    instruction_message = HumanMessage(
        content="Du a tren ke hoach va yeu cau ban dau, hay cung cap ma HTML hoan chinh dap ung mo ta."
    )
    messages_with_instruction = list(state["messages"]) + [instruction_message]
    result_state = invoke_with_retry(
        agent,
        {"messages": messages_with_instruction},
        state,
        "Code Agent",
    )
    if isinstance(result_state, dict) and "messages" in result_state:
        state["messages"] = result_state["messages"]
    else:
        state["messages"] = messages_with_instruction
    last_ai_message = next(
        (msg for msg in reversed(state["messages"]) if isinstance(msg, AIMessage)),
        None,
    )
    if last_ai_message is None:
        raise RuntimeError("Code Agent did not return an AIMessage response.")
    state["agent_response"] = last_ai_message.content
    state["code_output"] = last_ai_message.content
    state["agent_last"] = "code_agent"
    print_colored(f"Code Agent Response:\n {last_ai_message.content}", "yellow")
    return state



# end agent
def final_agent(state: AgentState) -> AgentState:
    print_colored("Final Agent Invoked", "green")

    llm = create_agent_basic(model=FinalResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_FINAL_AGENT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                "Dựa trên toàn bộ hội thoại, hãy tạo câu trả lời cuối cùng cho người dùng và cung cấp mã HTML đã tổng hợp.",
            ),
        ]
    )
    chain = prompt | llm
    response = invoke_with_retry(
        chain,
        {"messages": state["messages"]},
        state,
        "Final Agent",
        reminder="Please resend the final response using the expected JSON schema.",
    )
    state["final_response"] = response
    state["agent_last"] = "final_agent"

    summary_chunks = []
    if response.message:
        summary_chunks.append(response.message)
    if response.html:
        summary_chunks.append(f"HTML Output:\n{response.html}")
    if summary_chunks:
        state["messages"].append(AIMessage(content="\n\n".join(summary_chunks)))
    print_colored(f"Final Agent Response:\n {response}", "yellow")
    return state

def router_agent(state: AgentState) -> AgentState:
    print_colored("Router Agent Invoked", "green")
    llm = create_agent_basic(model=RouterResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_ROUTER_AGENT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                "Agent vừa hoàn thành: {agent_last}. Dựa trên tiến trình hiện tại, hãy quyết định agent tiếp theo cần thực hiện và giải thích ngắn gọn.",
            ),
        ]
    )
    chain = prompt | llm
    response = invoke_with_retry(
        chain,
        {
            "messages": state["messages"],
            "agent_last": state.get("agent_last", "unknown"),
        },
        state,
        "Router Agent",
        reminder="Vui lòng trả JSON đúng schema RouterResponse.",
    )
    state["route_response"] = response
    decision_summary = (
        f"Router quyết định chuyển từ {response.agent_current} sang {response.next_agent}."
    )
    if response.reason:
        decision_summary += f" Lý do: {response.reason}"
    state["messages"].append(AIMessage(content=decision_summary))
    state["agent_last"] = "router_agent"
    print_colored(f"Router Agent Response:\n {response}", "yellow")
    return state








