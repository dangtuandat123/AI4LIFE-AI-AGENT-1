from pydantic import BaseModel
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain.agents import create_agent


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"
class CheckBudgetResponse(BaseModel):
    name: str
    email: str
    phone: str

# 1) Dùng ChatOllama (instance), KHÔNG dùng chuỗi "openai:..."
llm = ChatOllama(model="gpt-oss:20b-cloud", temperature=0.7)

# 2) Tạo agent với ToolStrategy (cần model + adapter hỗ trợ bind_tools)
agent = create_agent(
    llm,
    tools=[search],
    response_format=ToolStrategy(CheckBudgetResponse),
    debug=True
)

out = agent.invoke({
    "messages": [{"role": "user",
                  "content": "Extract contact info from: John Doe, john@example.com, (555) 123-4567"}]
})

# 3) Prebuilt agent sẽ trả structured_response trong state
info = out.get("structured_response")  # ContactInfo(...)
print(info)
