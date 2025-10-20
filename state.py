from typing import List, Optional, Any, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from typing import List, Optional, Any, Literal

class FinalResponse(BaseModel):
    message: Optional[str] = Field(description="Lời giải thích ngắn gọn, thân thiện dành cho người dùng.")
    html: Optional[str] = Field(description="Nội dung HTML.")
   
class RouterResponse(BaseModel):
    agent_current: Literal["planner_agent", "code_agent", "final_agent", "router_agent"] = Field(description="agent hiện tại đang thực thi.")
    next_agent: Literal["final_agent", "code_agent"] = Field(description="agent tiếp theo sẽ thực hiện.")
    reason: Optional[str] = Field(description="Lý do chuyển đổi agent, nếu có.")

class AgentState(TypedDict, total=False):
    messages: List[BaseMessage]
    route_response: RouterResponse
    retrieved_docs: List[Any] 
    agent_response: Optional[str]
    final_response: Optional[FinalResponse]
    planner_response: Optional[str]
    code_output: Optional[str]
    agent_last: Optional[str]
