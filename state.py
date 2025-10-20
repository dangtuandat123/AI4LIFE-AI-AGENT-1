from typing import List, Optional, Any, Literal, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage

class FinalResponse(BaseModel):
    message: Optional[str] = Field(description="Lời giải thích ngắn gọn, thân thiện dành cho người dùng.")
    status: bool = Field(description="raw_input có đầy đủ thông tin hay không.")
   
class RouterResponse(BaseModel):
    agent_current: Literal["node_get_schema", "router_agent", "query_agent", "final_agent"] = Field(description="agent hiện tại đang thực thi.")
    next_agent: Literal["final_agent", "query_agent"] = Field(description="agent tiếp theo sẽ thực hiện.")
    reason: Optional[str] = Field(description="Lý do chuyển đổi agent, nếu có.")
    null_fields: Optional[List[str]] = Field(description="Danh sách các trường dữ liệu còn thiếu so với schema.")

class AgentState(TypedDict, total=False):
    messages: List[BaseMessage]
    route_response: RouterResponse
    agent_response: Optional[str]
    final_response: Optional[FinalResponse]
    agent_last: Optional[str]
    schema_info: Optional[Any]
    raw_input: Optional[str]
