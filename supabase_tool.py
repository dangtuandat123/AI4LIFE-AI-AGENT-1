import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from supabase import create_client
from langchain_ollama import OllamaEmbeddings


load_dotenv()
SUPABASE_URL = "https://qubthigmzdkdfqrztjhm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF1YnRoaWdtemRrZGZxcnp0amhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA4NjM4ODAsImV4cCI6MjA3NjQzOTg4MH0.DcRHTJ86LguX7U4EqiG-qrHlIs4D7AZQiVz_Zs0-SJs"
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large")


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
emb = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def embed_text(text: str) -> List[float]:
    """Sinh vector embedding cho 1 đoạn text."""
    return emb.embed_documents([text])[0]


def embed_query(text: str) -> List[float]:
    """Sinh vector embedding cho câu truy vấn."""
    return emb.embed_query(text)


def insert_activity(
    employee_id: str,
    project_code: str,
    activity_date_iso: str,
    activity_type: str,
    description: str,
    amount_value: float = 0.0,
    revenue_value: float = 0.0,
    status: str = "pending",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tạo activity mới: embed description và lưu vào cột activities.embedding (vector 1024 chiều).
    """
    vec = embed_text(description)
    payload = {
        "employee_id": employee_id,
        "project_code": project_code,
        "activity_date": activity_date_iso,
        "activity_type": activity_type,
        "description": description,
        "amount_value": amount_value,
        "revenue_value": revenue_value,
        "status": status,
        "notes": notes,
        "embedding": vec,
    }
    res = supabase.table("activities").insert(payload).execute()
    if not res.data:
        raise RuntimeError("Insert activity thất bại")
    return res.data[0]


def backfill_activity_embeddings(batch_size: int = 100) -> int:
    """
    Lặp qua các activities.embedding IS NULL, embed description rồi update.
    Trả về số bản ghi đã cập nhật.
    """
    updated = 0
    while True:
        resp = (
            supabase.table("activities")
            .select("id, description")
            .is_("embedding", "null")
            .order("id", desc=False)
            .limit(batch_size)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break

        texts = [r["description"] for r in rows]
        vectors = emb.embed_documents(texts)

        for r, vec in zip(rows, vectors):
            supabase.table("activities").update({"embedding": vec}).eq("id", r["id"]).execute()
            updated += 1

    return updated


def search_activities(
    query: str,
    k: int = 5,
    team_name: Optional[str] = None,
    threshold: float = 0.0,
    project_code: Optional[str] = None,
    status: Optional[str] = None,
    employee_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Gọi hàm RPC match_activities (vector 1024 chiều).
    """
    q_vec = embed_query(query)
    filt: Dict[str, Any] = {}
    if team_name:
        filt["team_name"] = team_name
    if project_code:
        filt["project_code"] = project_code
    if status:
        filt["status"] = status
    if employee_id:
        filt["employee_id"] = employee_id
    if date_from:
        filt["date_from"] = date_from
    if date_to:
        filt["date_to"] = date_to

    payload = {
        "query_embedding": q_vec,
        "match_count": k,
        "match_threshold": threshold,
        "filter": filt or {},
    }
    res = supabase.rpc("match_activities", payload).execute()
    return res.data or []


def summarize_spending_by_project() -> List[Dict[str, Any]]:
    """
    Lấy dữ liệu từ bảng activities thông qua Supabase REST và tổng hợp trên client.
    """
    res = (
        supabase.table("activities")
        .select("project_code, amount_value, revenue_value, status")
        .execute()
    )
    rows = res.data or []
    summary: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        project_code = row["project_code"]
        amount = float(row.get("amount_value") or 0)
        revenue = float(row.get("revenue_value") or 0)
        status = (row.get("status") or "").lower()
        project_summary = summary.setdefault(
            project_code,
            {
                "project_code": project_code,
                "approved_spent": 0.0,
                "pending_amount": 0.0,
                "approved_revenue": 0.0,
            },
        )
        if status == "approved":
            project_summary["approved_spent"] += amount
            project_summary["approved_revenue"] += revenue
        elif status == "pending":
            project_summary["pending_amount"] += amount
    return list(summary.values())


def describe_workspace() -> str:
    """
    Gọi hàm describe_workspace trong DB để lấy thông tin schema + số lượng bản ghi.
    Trả về chuỗi có định dạng:
      Table: <table> | rows=<row_count> | note=<table_comment>
        - <column_name>: <data_type> (nullable=<is_nullable>, default=<column_default>, note=<comment>)
        …
    """
    res = supabase.rpc("describe_workspace").execute()
    schema_info = res.data or []

    lines: List[str] = []
    for tbl in schema_info:
        lines.append(f"Table: {tbl.get('table')} | rows={tbl.get('row_count')} | note={tbl.get('table_comment')}")
        for col in tbl.get("columns", []):
            lines.append(
                f"  - {col.get('column_name')}: {col.get('data_type')} "
                f"(nullable={col.get('is_nullable')}, default={col.get('column_default')}, note={col.get('comment')})"
            )
    return "\n".join(lines)


def run_sql_query(sql: str) -> List[Dict[str, Any]]:
    """
    Gọi hàm query_sql (SELECT only) để lấy dữ liệu dạng list[dict] cho agent.
    """
    res = supabase.rpc("query_sql", {"p_sql": sql}).execute()
    return res.data or []


if __name__ == "__main__":
    n = backfill_activity_embeddings(batch_size=100)
    print(f"Backfill done. Updated embeddings for {n} activities.")

    print("\n--- RPC search (team=Sales, status=approved) ---")
    results = search_activities(
        "tìm chiến dịch chạy quảng cáo",
        k=5,
        # team_name="Sales",
        # status="approved",
        threshold=0.5,
    )
    for i, r in enumerate(results, 1):
        print(
            f"[{i}] sim={r['similarity']:.4f} | id={r['id']} | team={r['team_name']} | "
            f"employee={r['employee_name']} | {r['activity_type']} | "
            f"chi={r.get('amount_value', 0)} | doanh_thu={r.get('revenue_value', 0)} | {r['description']}"
        )

    summary_rows = summarize_spending_by_project()
    print("\n--- Tổng hợp chi tiêu theo project_code (client-side) ---")
    for row in summary_rows:
        print(row)

    schema_info = describe_workspace()
    print(schema_info)


    sql_demo = """
        select e.team_name,
               count(distinct a.id) as activity_count,
               sum(a.amount_value) as total_cost,
               sum(a.revenue_value) as total_revenue
        from public.activities a
        join public.employees e on e.id = a.employee_id
        group by e.team_name
        order by e.team_name
    """
    sql_rows = run_sql_query(sql_demo)
    print("\n--- SQL query qua query_sql (agent-ready) ---")
    for row in sql_rows:
        print(row)

    complex_queries = [
        (
            "Tổng quan ngân sách theo dự án",
            """
            select
                b.project_code,
                b.team_name,
                b.budget_limit,
                sum(case when a.status = 'approved' then a.amount_value else 0 end) as approved_spent,
                sum(case when a.status = 'approved' then a.revenue_value else 0 end) as approved_revenue,
                sum(case when a.status = 'pending' then a.amount_value else 0 end) as pending_cost,
                count(*) filter (where a.status = 'pending') as pending_activities,
                round(
                    case
                        when b.budget_limit > 0
                        then 100 * sum(case when a.status = 'approved' then a.amount_value else 0 end) / b.budget_limit
                        else 0
                    end,
                    2
                ) as budget_utilization_pct
            from public.budgets b
            left join public.activities a on a.project_code = b.project_code
            group by b.project_code, b.team_name, b.budget_limit
            order by b.team_name, b.project_code
            """
        ),
        (
            "Top nhân viên theo doanh thu đã duyệt",
            """
            select
                e.full_name,
                e.team_name,
                count(*) filter (where a.status = 'approved') as approved_activities,
                sum(a.revenue_value) filter (where a.status = 'approved') as approved_revenue,
                sum(a.amount_value) filter (where a.status = 'approved') as approved_cost
            from public.employees e
            join public.activities a on a.employee_id = e.id
            group by e.full_name, e.team_name
            having sum(a.revenue_value) filter (where a.status = 'approved') > 0
            order by approved_revenue desc
            limit 5
            """
        ),
        (
            "Dòng tiền theo ngày (chi / thu đã duyệt)",
            """
            select
                date_trunc('day', a.activity_date) as activity_day,
                sum(a.amount_value) filter (where a.status = 'approved') as approved_cost,
                sum(a.revenue_value) filter (where a.status = 'approved') as approved_revenue,
                count(*) filter (where a.status = 'approved') as approved_count
            from public.activities a
            group by activity_day
            order by activity_day desc
            limit 15
            """
        ),
        (
            "Danh sách pending vượt ngưỡng cảnh báo",
            """
            select
                a.id,
                a.activity_date,
                e.full_name,
                e.team_name,
                a.project_code,
                a.amount_value,
                b.budget_limit,
                b.warn_percent,
                sum(a2.amount_value) filter (where a2.status = 'approved') as approved_spent_to_date,
                a.notes
            from public.activities a
            join public.employees e on e.id = a.employee_id
            join public.budgets b on b.project_code = a.project_code
            left join public.activities a2
                on a2.project_code = a.project_code
               and a2.status = 'approved'
            where a.status = 'pending'
            group by
                a.id,
                a.activity_date,
                e.full_name,
                e.team_name,
                a.project_code,
                a.amount_value,
                b.budget_limit,
                b.warn_percent,
                a.notes
            having
                b.budget_limit > 0
                and (sum(a2.amount_value) filter (where a2.status = 'approved') + a.amount_value)
                    > b.budget_limit * (1 - b.warn_percent / 100.0)
            order by a.activity_date desc
            """
        ),
        (
            "Hiệu suất theo team (chi phí / doanh thu / tỉ lệ phê duyệt)",
            """
            with team_stats as (
                select
                    e.team_name,
                    count(*) as total_activities,
                    count(*) filter (where a.status = 'approved') as approved_count,
                    count(*) filter (where a.status = 'pending') as pending_count,
                    sum(a.amount_value) filter (where a.status = 'approved') as approved_cost,
                    sum(a.revenue_value) filter (where a.status = 'approved') as approved_revenue
                from public.activities a
                join public.employees e on e.id = a.employee_id
                group by e.team_name
            )
            select
                team_name,
                total_activities,
                approved_count,
                pending_count,
                approved_cost,
                approved_revenue,
                round(
                    case when total_activities > 0
                         then 100.0 * approved_count / total_activities
                         else 0 end,
                    2
                ) as approval_rate_pct
            from team_stats
            order by team_name
            """
        )
    ]

    for title, sql in complex_queries:
        rows = run_sql_query(sql)
        print(f"\n--- {title} ---")
        if rows:
            for row in rows:
                print(row)
        else:
            print("  (no data)")
