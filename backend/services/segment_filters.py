from typing import Any, Dict


def build_segment_sql(filter_json: Dict[str, Any]):
    clauses = []
    values = []

    if "city" in filter_json:
        clauses.append(f"city = ${len(values)+1}")
        values.append(filter_json["city"])

    if "min_spent" in filter_json:
        clauses.append(f"total_spent >= ${len(values)+1}")
        values.append(filter_json["min_spent"])

    if "max_spent" in filter_json:
        clauses.append(f"total_spent <= ${len(values)+1}")
        values.append(filter_json["max_spent"])

    if "min_orders" in filter_json:
        clauses.append(f"total_orders >= ${len(values)+1}")
        values.append(filter_json["min_orders"])

    if "last_order_before" in filter_json:
        clauses.append(f"last_order_date <= ${len(values)+1}")
        values.append(filter_json["last_order_before"])

    where_clause = " AND ".join(clauses)
    if not where_clause:
        where_clause = "TRUE"

    return where_clause, values
