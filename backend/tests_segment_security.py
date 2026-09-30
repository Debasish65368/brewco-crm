import sys
try:
    from pydantic import ValidationError
except ImportError:
    print("Run this test with an environment that has pydantic installed.")
    sys.exit(1)

from fastapi import HTTPException
from services.segment_filters import build_segment_sql

def run_test(name: str, filter_json: dict, expected_fail: bool):
    did_fail = False
    sql = ""
    params = []
    
    try:
        sql, params = build_segment_sql(filter_json)
    except Exception as e:
        did_fail = True

    if did_fail == expected_fail:
        print(f"[PASS] {name}")
        if not did_fail:
            print(f"       SQL: {sql} | Params: {params}")
        return True
    else:
        print(f"[FAIL] {name} | Expected fail: {expected_fail}, Got: {did_fail}")
        return False

tests = [
    {
        "name": "empty filter",
        "filter_json": {},
        "expected_fail": True
    },
    {
        "name": "negative cluster_id",
        "filter_json": {"cluster_id": -1},
        "expected_fail": True
    },
    {
        "name": "unknown filter",
        "filter_json": {"banana": "something"},
        "expected_fail": True
    },
    {
        "name": "wrong value type (date)",
        "filter_json": {"last_order_before": "not-a-date"},
        "expected_fail": True
    },
    {
        "name": "wrong value type (int)",
        "filter_json": {"cluster_id": "abc"},
        "expected_fail": True
    },
    {
        "name": "negative min_spent",
        "filter_json": {"min_spent": -500},
        "expected_fail": True
    },
    {
        "name": "negative min_orders",
        "filter_json": {"min_orders": -2},
        "expected_fail": True
    },
    {
        "name": "min_spent > max_spent",
        "filter_json": {"min_spent": 5000, "max_spent": 1000},
        "expected_fail": True
    },
    {
        "name": "SQL injection-style value",
        "filter_json": {"city": "Delhi'; DROP TABLE customers; --"},
        "expected_fail": False
    },
    {
        "name": "valid city filter",
        "filter_json": {"city": "Delhi"},
        "expected_fail": False
    },
    {
        "name": "valid monetary filter",
        "filter_json": {"min_spent": 5000},
        "expected_fail": False
    },
    {
        "name": "valid order-count filter",
        "filter_json": {"min_orders": 3},
        "expected_fail": False
    },
    {
        "name": "valid date filter",
        "filter_json": {"last_order_before": "2025-01-01"},
        "expected_fail": False
    },
    {
        "name": "valid combined filter",
        "filter_json": {"city": "Delhi", "min_spent": 5000},
        "expected_fail": False
    }
]

def main():
    print("Running Security Regression Tests for Segment Filters...")
    all_passed = True
    for t in tests:
        if not run_test(t["name"], t["filter_json"], t["expected_fail"]):
            all_passed = False
            
    if all_passed:
        print("All tests passed.")
        sys.exit(0)
    else:
        print("Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
