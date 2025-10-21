from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from prompts import (
    SYSTEM_PROMPT_FINAL_AGENT,
    SYSTEM_PROMPT_PLANNER_AGENT,
    SYSTEM_PROMPT_QUERY_AGENT,
    SYSTEM_PROMPT_ROUTER_AGENT,
)
from state import AgentState, FinalResponse, RouterResponse
from supabase_tool import describe_workspace
from tools import run_python_code, run_supabase_sql, search_web
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

    llm = create_agent_basic(model=RouterResponse)
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


def planner_agent(state: AgentState) -> AgentState:
    """Outline the plan for the upcoming query steps."""
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
    state["agent_last"] = "planner_agent"
    print_colored(f"Planner Agent Response:\n {response.content}", "yellow")
    return state


def query_agent(state: AgentState) -> AgentState:
    """Generate and execute Supabase SQL when enough data is available."""
    print_colored("Query Agent Invoked", "green")

    agent = create_agent_react(
        tools=[search_web, run_supabase_sql, run_python_code],
        system_prompt=SYSTEM_PROMPT_QUERY_AGENT,
    )
    conversation: List[BaseMessage] = list(state["messages"])
    schema_info = state.get("schema_info", "")
    if schema_info:
        conversation.append(
            HumanMessage(
                content=(
                    "Lưu ý: đây là schema Supabase hiện tại để tham chiếu khi lập kế hoạch và truy vấn:\n"
                    f"{schema_info}"
                )
            )
        )
    conversation.append(
        HumanMessage(
            content=(
                "Dựa vào yêu cầu ban đầu, hãy tạo câu lệnh SQL để truy vấn cơ sở dữ liệu Supabase "
                "và kiểm tra ngân sách hiện tại có hợp lý hay không. "
                "Nếu dữ liệu Supabase chưa đủ, hãy dùng thêm công cụ search_web để tìm thông tin hỗ trợ. "
                "Nếu công cụ báo lỗi, bạn PHẢI đọc kỹ thông báo, sửa lại câu truy vấn và chạy lại. "
                "Mọi phản hồi phải bằng tiếng Việt tự nhiên."
            )
        )
    )

    max_attempts = 3
    last_ai_message: AIMessage | None = None

    for attempt in range(1, max_attempts + 1):
        result_state = invoke_with_retry(
            agent,
            {"messages": conversation},
            state,
            "Query Agent",
        )
        if isinstance(result_state, dict) and "messages" in result_state:
            conversation = result_state["messages"]

        last_ai_message = next(
            (msg for msg in reversed(conversation) if isinstance(msg, AIMessage)),
            None,
        )
        if last_ai_message is None:
            raise RuntimeError("Query Agent did not return an AIMessage response.")

        if "[ERROR] Supabase query failed" in last_ai_message.content and attempt < max_attempts:
            print_colored(
                f"Query Agent detected SQL error, prompting retry (attempt {attempt + 1}/{max_attempts}).",
                "red",
            )
            conversation.append(
                HumanMessage(
                    content=(
                        "Công cụ Supabase báo lỗi ở truy vấn vừa rồi. "
                        "Hãy phân tích thông báo lỗi, điều chỉnh câu SQL cho đúng cú pháp và chạy lại ngay."
                    )
                )
            )
            continue
        break

    state["messages"] = conversation
    state["agent_response"] = last_ai_message.content if last_ai_message else None
    state["agent_last"] = "query_agent"
    print_colored(f"Query Agent Response:\n {state['agent_response']}", "yellow")
    return state


def final_agent(state: AgentState) -> AgentState:
    """Produce the user-facing response following the router decision."""
    print_colored("Final Agent Invoked", "green")

    llm = create_agent_basic(model=FinalResponse)
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
