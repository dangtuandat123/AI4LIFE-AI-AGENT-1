from langchain_core.messages import HumanMessage

from graph import compiled_app
from state import AgentState


def run_app(user_input: str) -> AgentState:
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_input)],
        "raw_input": user_input,
    }
    final_state = compiled_app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    sample_report = (
        "Ngày 22/09/2025 lúc 09:00 UTC, nhân viên 11111111-1111-1111-1111-111111111111 "
        "trong dự án SALES_SEP25 đã ký hợp đồng trị giá 180.000.000 VND với Công ty Z, "
        "thu 30% đặt cọc tương đương 54.000.000 VND và ghi nhận doanh thu này trong CRM "
        "với trạng thái approved."
    )
    result_state = run_app(sample_report)
    final_response = result_state.get("final_response")
    if final_response:
        print(f"status={final_response.status} | message={final_response.message}")
    else:
        print("Không tạo được phản hồi cuối cùng.")
