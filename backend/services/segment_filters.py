from typing import Any, Dict
from pydantic import ValidationError
from fastapi import HTTPException
from schemas import SegmentFilterSchema

def build_segment_sql(filter_json: Dict[str, Any]):
    try:
        validated = SegmentFilterSchema.model_validate(filter_json)
    except ValidationError as e:
        # We can raise an HTTPException so the API fails cleanly
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid segment filter")
    
    clauses = []
    values = []

    if validated.city is not None:
        clauses.append(f"LOWER(city) = LOWER(${len(values)+1})")
        values.append(validated.city)

    if validated.cluster_id is not None:
        clauses.append(f"cluster_id = ${len(values)+1}")
        values.append(validated.cluster_id)

    if validated.min_spent is not None:
        clauses.append(f"total_spent >= ${len(values)+1}")
        values.append(validated.min_spent)

    if validated.max_spent is not None:
        clauses.append(f"total_spent <= ${len(values)+1}")
        values.append(validated.max_spent)

    if validated.min_orders is not None:
        clauses.append(f"total_orders >= ${len(values)+1}")
        values.append(validated.min_orders)

    if validated.last_order_before is not None:
        clauses.append(f"last_order_date <= ${len(values)+1}")
        values.append(validated.last_order_before)

    where_clause = " AND ".join(clauses)
    if not where_clause:
        raise HTTPException(status_code=400, detail="Segment must contain at least one filter condition.")

    return where_clause, values
