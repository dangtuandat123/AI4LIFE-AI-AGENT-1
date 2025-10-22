from typing import Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

class FinalResponse(BaseModel):
    message: Optional[str] = Field(description="Lời giải thích ngắn gọn, thân thiện dành cho người dùng.")
    status: bool = Field(description="raw_input có đầy đủ thông tin hay không.")

class CheckBudgetResponse(BaseModel):
    message: str = Field(description="Tóm tắt rõ ràng kết quả kiểm tra ngân sách hoặc hướng dẫn cần thực hiện.")
    status: bool = Field(description="Ngân sách hợp lệ hay cần xử lý thêm.")
   #
class RouterResponse(BaseModel):
    agent_current: Literal["node_get_schema", "router_agent", "checkbudget_agent", "final_agent"] = Field(description="agent hiện tại đang thực thi.")
    next_agent: Literal["checkbudget_agent", "final_agent"] = Field(description="agent tiếp theo sẽ thực hiện.")
    reason: Optional[str] = Field(description="Lý do chuyển đổi agent, nếu có.")

class CheckDataResponse(BaseModel):
    activity_date : Optional[str] = Field(default=None, description="Ngày diễn ra hoạt động")
    activity_type:  Optional[Literal["expense","revenue","task"]] = Field(default=None, description="Loại hoạt động: chi phí, doanh thu, hoặc tác vụ (expense,revenue,task)")
    description:  Optional[str] = Field(default=None, description="Mô tả chi tiết của hoạt động.")
    amount_value:  Optional[float] = Field(default=None, description="Giá trị chi phí.")
    revenue_value:  Optional[float] = Field(default=None,description="Giá trị doanh thu ghi nhận.")
    notes:  Optional[str] = Field(default=None, description="Ghi chú bổ sung")
    
class AgentState(TypedDict, total=False):
    messages: List[BaseMessage]
    route_response: Optional[RouterResponse]
    checkdata_response: Optional[CheckDataResponse]
    agent_response: Optional[Dict[str, Any]]
    checkbudget_response: Optional[CheckBudgetResponse]
    final_response: Optional[FinalResponse]
    agent_last: Optional[str]
    input_text: Optional[str]
