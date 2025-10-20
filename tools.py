import json
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from postgrest.exceptions import APIError

from supabase_tool import run_sql_query
from utils import print_colored
try:
    from langchain_tavily import TavilySearch as _TavilySearchTool
except ImportError:  # Fallback for older environments
    from langchain_community.tools import TavilySearchResults as _TavilySearchTool


load_dotenv()


def _ensure_tavily_key() -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is missing. Please set it in your environment or .env file."
        )
    # Ensure downstream libraries can pick it up even if load_dotenv runs late.
    os.environ.setdefault("TAVILY_API_KEY", api_key)
    return api_key


def _run_tavily(query: str) -> str:
    _ensure_tavily_key()
    search_tool = _TavilySearchTool(max_results=5)
    result = None
    if hasattr(search_tool, "invoke"):
        result = search_tool.invoke({"query": query})
    elif hasattr(search_tool, "run"):
        result = search_tool.run(query)
    else:
        raise AttributeError("Tavily search tool does not support invoke or run.")
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)





# khai bao structore cho tool 
class SearchWebArgs(BaseModel):
    query: str = Field(..., description="Câu truy vấn để tìm kiếm trên Internet bằng Tavily.")

class RunSupabaseSQLArgs(BaseModel):
    sql_query: str = Field(..., description="Câu lệnh SQL cần thực thi trên cơ sở dữ liệu Supabase.")



#khai bao tool 

@tool(
    "search_web",
    description="Tìm kiếm thông tin trên Internet bằng công cụ Tavily. Trả về JSON string hoặc kết quả tìm kiếm dưới dạng text.",
    args_schema=SearchWebArgs,
    return_direct=True
)
def search_web(query: str) -> str:
    """Tìm kiếm thông tin trên Internet bằng Tavily."""
    print(f"[Tool] search_web called with query: {query}")
    results = _run_tavily(query)
    print_colored(results, "magenta")
    print(f"[Tool] search_web completed")
    return results


@tool(
    "run_supabase_sql",
    description="Kiểm tra ngân sách có phù hợp hay không dựa trên các tiêu chí đã cho.",
    return_direct=True,
    args_schema=RunSupabaseSQLArgs,
)
def run_supabase_sql(sql_query: str) -> str:
    raw_sql = sql_query.strip()
    if raw_sql.endswith(";"):
        raw_sql = raw_sql[:-1].rstrip()
    print(f"[Tool] run_supabase_sql called with query: {raw_sql}")
    try:
        results = run_sql_query(raw_sql)
        pretty_results = json.dumps(results, ensure_ascii=False)
        print_colored(pretty_results, "magenta")
        print(f"[Tool] run_supabase_sql completed")
        return pretty_results
    except APIError as exc:
        error_payload = {
            "error": exc.message or "Supabase API error",
            "code": exc.code,
            "details": exc.details,
            "hint": exc.hint,
            "sql": raw_sql,
        }
        pretty_error = json.dumps(error_payload, ensure_ascii=False)
        print_colored(pretty_error, "red")
        print(f"[Tool] run_supabase_sql failed")
        return f"[ERROR] Supabase query failed: {pretty_error}"
