import json
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from prompts import (
    SYSTEM_PROMPT_CHECKBUDGET_AGENT,
    SYSTEM_PROMPT_FINAL_AGENT,
    SYSTEM_PROMPT_ROUTER_AGENT,
)
from state import AgentState, FinalResponse, RouterResponse, CheckbudgetResponse
from supabase_tool import describe_workspace, rebuild_tailieu_index
from tools import rag_tailieu, run_python_code, run_supabase_sql, search_web
from utils import create_agent_basic, create_agent_react, invoke_with_retry, print_colored


def node_get_schema(state: AgentState) -> AgentState:
    """Fetch Supabase schema metadata before routing."""
    try:
        schema_info = describe_workspace()
        print_colored("Đã lấy schema Supabase thành công.", "cyan")
    except Exception as exc:  # pragma: no cover - defensive logging
        schema_info = f"Không thể lấy schema Supabase do lỗi: {exc}"
        print_colored(schema_info, "red")
        state["messages"].append(
            AIMessage(
                content="Không thể lấy schema Supabase ở thời điểm hiện tại. "
                "Vui lòng thử lại sau hoặc kiểm tra cấu hình kết nối."
            )
        )
    state["schema_info"] = schema_info
    state["agent_last"] = "node_get_schema"
    return state


def router_agent(state: AgentState) -> AgentState:
    """Decide whether to collect more info or run queries."""
    print_colored("Router Agent Invoked", "green")

    llm = create_agent_basic(response_struct=RouterResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_ROUTER_AGENT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                "Agent vừa hoàn thành: {agent_last}.\n"
                "Schema Supabase hiện có:\n{schema_info}\n\n"
                "Báo cáo raw_input của nhân viên:\n{raw_input}",
            ),
        ]
    )
    chain = prompt | llm
    response = invoke_with_retry(
        chain,
        {
            "messages": state["messages"],
            "agent_last": state.get("agent_last", "unknown"),
            "schema_info": state.get("schema_info", "Không có dữ liệu schema."),
            "raw_input": state.get("raw_input", ""),
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
    if response.null_fields:
        decision_summary += f" (Thiếu thông tin: {', '.join(response.null_fields)})"
    state["messages"].append(AIMessage(content=decision_summary))
    state["agent_last"] = "router_agent"
    print_colored(f"Router Agent Response:\n {response}", "yellow")
    return state



def checkbudget_agent(state: AgentState) -> AgentState:
    """Hybrid ReAct agent có RAG tailieu.txt và kiểm tra ngân sách."""
    print_colored("CheckBudget Agent Invoked", "green")

    try:
        indexed = rebuild_tailieu_index()
        if indexed:
            print_colored(
                f"Đồng bộ tailieu.txt lên Supabase ({indexed} đoạn mới).",
                "cyan",
            )
    except Exception as exc:  # pragma: no cover - defensive logging
        error_msg = (
            "Không thể đồng bộ tailieu.txt lên vector store. "
            f"Vui lòng kiểm tra Supabase: {exc}"
        )
        print_colored(error_msg, "red")
        state["messages"].append(AIMessage(content=error_msg))

    llm = create_agent_react(
        tools=[rag_tailieu, run_python_code],
        response_struct=CheckbudgetResponse,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_CHECKBUDGET_AGENT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                "Schema Supabase hiện có:\n{schema_info}\n\n"
                "Báo cáo raw_input của nhân viên:\n{raw_input}",
            ),
        ]
    )
    chain = prompt | llm

    response = invoke_with_retry(
        chain,
        {
            "messages": state["messages"],
            "schema_info": state.get("schema_info", "Không có dữ liệu schema."),
            "raw_input": state.get("raw_input", ""),
        },
        state,
        "CheckBudget Agent",
    )
    print_colored(response, "cyan")

   

    state["messages"] = response
    state["agent_response"] = response.content
    state["agent_last"] = "checkbudget_agent"
    print_colored(f"CheckBudget Agent Response:\n {response.content}", "yellow")
    return state


def final_agent(state: AgentState) -> AgentState:
    """Produce the user-facing response following the router decision."""
    print_colored("Final Agent Invoked", "green")

    llm = create_agent_basic(response_struct=FinalResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT_FINAL_AGENT),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                "Dựa trên toàn bộ hội thoại, hãy tạo câu trả lời cuối cùng cho người dùng.",
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

    if response.message:
        state["messages"].append(AIMessage(content=response.message))

    print_colored(f"Final Agent Response:\n {response}", "yellow")
    return state
