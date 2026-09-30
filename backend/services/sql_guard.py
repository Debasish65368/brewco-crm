from pydantic import ValidationError
import json
from typing import Tuple, List, Any

# We expect the structured JSON dict here
def build_analytics_query(spec_dict: dict) -> Tuple[bool, str, str, List[Any]]:
    """
    Parses a dictionary into QuerySpec and builds parameterized SQL.
    Returns: (is_valid, error_reason, sql_string, parameters_list)
    """
    try:
        from schemas import QuerySpec
        spec = QuerySpec.model_validate(spec_dict)
    except ValidationError as e:
        return False, f"Invalid query specification: {e}", "", []
    except Exception as e:
        return False, f"Failed to parse query specification: {e}", "", []

    try:
        tables = spec.tables
        if not tables:
            return False, "At least one table must be specified.", "", []

        # Start building the SQL
        # We will use parameterized values for filters
        params = []
        
        # 1. SELECT clause
        select_parts = []
        for col in spec.select:
            col_ref = f"{col.table}.{col.column}"
            if col.agg:
                select_parts.append(f"{col.agg}({col_ref})")
            else:
                select_parts.append(col_ref)
        
        select_clause = ", ".join(select_parts)
        
        # 2. FROM clause
        # If multiple tables, we do a basic CROSS JOIN or implicit join.
        # Wait, the prompt says "arbitrary joins" are forbidden. But users might ask cross-table queries.
        # Let's see: typically CRM has customers and orders.
        # If tables contain both "customers" and "orders", we should join on customers.id = orders.customer_id
        from_clause = tables[0]
        if len(tables) > 1:
            # Simple predefined joins to avoid arbitrary join logic
            join_parts = [tables[0]]
            for i in range(1, len(tables)):
                t1, t2 = tables[i-1], tables[i]
                if {"customers", "orders"}.issubset({t1, t2}):
                    join_parts.append(f"JOIN {t2} ON customers.id = orders.customer_id")
                elif {"segments", "campaigns"}.issubset({t1, t2}):
                    join_parts.append(f"JOIN {t2} ON segments.id = campaigns.segment_id")
                elif {"campaigns", "communications"}.issubset({t1, t2}):
                    join_parts.append(f"JOIN {t2} ON campaigns.id = communications.campaign_id")
                elif {"customers", "communications"}.issubset({t1, t2}):
                    join_parts.append(f"JOIN {t2} ON customers.id = communications.customer_id")
                else:
                    return False, f"Unsupported join between {t1} and {t2}", "", []
            from_clause = " ".join(join_parts)
            
        sql = f"SELECT {select_clause} FROM {from_clause}"
        
        # 3. WHERE clause
        if spec.where:
            where_parts = []
            for condition in spec.where:
                col_ref = f"{condition.table}.{condition.column}"
                if condition.operator in ('IS NULL', 'IS NOT NULL'):
                    where_parts.append(f"{col_ref} {condition.operator}")
                else:
                    params.append(condition.value)
                    param_idx = len(params)
                    where_parts.append(f"{col_ref} {condition.operator} ${param_idx}")
            sql += " WHERE " + " AND ".join(where_parts)
            
        # 4. GROUP BY clause
        if spec.group_by:
            group_parts = []
            for col in spec.group_by:
                col_ref = f"{col.table}.{col.column}"
                group_parts.append(col_ref)
            sql += " GROUP BY " + ", ".join(group_parts)
            
        # 5. ORDER BY clause
        if spec.order_by:
            order_parts = []
            for col in spec.order_by:
                col_ref = f"{col.table}.{col.column}"
                if col.agg:
                    order_parts.append(f"{col.agg}({col_ref}) {col.direction}")
                else:
                    order_parts.append(f"{col_ref} {col.direction}")
            sql += " ORDER BY " + ", ".join(order_parts)
            
        # 6. LIMIT clause
        sql += f" LIMIT {spec.limit}"
        
        return True, "", sql, params
        
    except Exception as e:
        return False, f"Error building SQL: {e}", "", []
