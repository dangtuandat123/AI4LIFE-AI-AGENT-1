from langchain_core.messages import HumanMessage

from graph import compiled_app
from state import AgentState


def run_app(user_input: str) -> AgentState:
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "input_text": user_input,
    }
    final_state = compiled_app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    sample_report = (
        "Ngày 22/09/2025 lúc 09:00 UTC, nhân viên 11111111-1111-1111-1111-111111111111 thuộc team sale. "
        "Hôm nay em hoàn thành 5 đơn hàng (doanh thu ~ 120 triệu VND) cho dự án Alpha, chi hết 3 triệu quảng cáo Facebook. "
        "activity_type: revenue"
    )
    result_state = run_app(sample_report)
    final_response = result_state.get("final_response")
    if final_response:
        print(f"status={final_response.status} | message={final_response.message}")
    else:
        print("K")
