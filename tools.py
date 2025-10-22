import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from postgrest.exceptions import APIError

from langchain_experimental.tools.python.tool import PythonREPLTool
from supabase_tool import rag_search_tailieu, rebuild_tailieu_index, run_sql_query
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


class ExecutePythonArgs(BaseModel):
    code: str = Field(
        ...,
        description=(
            "Đoạn mã Python ngắn (không import thư viện bên ngoài) dùng để tính toán, "
            "ví dụ tổng hợp số liệu, kiểm tra logic hoặc format dữ liệu. "
            "Phải an toàn, không được thao tác file hệ thống hoặc mạng."
        ),
    )


class RagTailieuArgs(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc từ khóa cần tìm trong tailieu.txt.")
    top_k: int = Field(default=4, ge=1, le=10, description="Số đoạn văn trả về (tối đa 10).")
    refresh_index: bool = Field(
        default=False,
        description="Đặt True nếu muốn xây lại index từ tailieu.txt trước khi tìm kiếm.",
    )

#khai bao tool 

@tool(
    "search_web",
    description="Tìm kiếm thông tin trên Internet bằng công cụ Tavily. Trả về JSON string hoặc kết quả tìm kiếm dưới dạng text.",
    args_schema=SearchWebArgs,
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


@tool(
    "run_python_code",
    description="Chạy nhanh một đoạn code Python thuần để tính toán hoặc biến đổi dữ liệu (dựa trên PythonREPLTool của LangChain).",
    args_schema=ExecutePythonArgs,
)
def run_python_code(code: str) -> str:
    """
    Execute a small Python snippet for calculations using LangChain's built-in Python REPL tool.
    """
    print(f"[Tool] run_python_code received:\n{code}")
    repl_tool = PythonREPLTool()
    try:
        output = repl_tool.run(code)
    except Exception as exc:  # pragma: no cover - guardrail
        error_msg = f"[ERROR] Python execution failed: {exc}"
        print_colored(error_msg, "red")
        return error_msg
    print_colored(output, "cyan")
    print("[Tool] run_python_code completed")
    return output


@tool(
    "rag_tailieu",
    description="Truy vấn tri thức nội bộ từ tailieu.txt thông qua Supabase vector store.",
    args_schema=RagTailieuArgs,
)
def rag_tailieu(query: str, top_k: int = 4, refresh_index: bool = False) -> str:
    """
    Tìm kiếm các đoạn văn bản liên quan trong tailieu.txt đã được index lên Supabase.
    """
    print(f"[Tool] rag_tailieu called with query: {query} | top_k={top_k} | refresh={refresh_index}")
    if refresh_index:
        rebuild_tailieu_index(force=True)
    results_raw = rag_search_tailieu(query, k=top_k, refresh=False)
    results = []
    for item in results_raw:
        entry: Dict[str, Any] = {"content": item.get("content")}
        score = item.get("score")
        if score is not None:
            entry["score"] = score
        results.append(entry)
    payload = json.dumps(results, ensure_ascii=False, indent=2)
    print_colored(payload, "magenta")
    print("[Tool] rag_tailieu completed")
    
    return payload
