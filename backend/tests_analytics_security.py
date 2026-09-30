import sys

try:
    from pydantic import ValidationError
except ImportError:
    print("Run this test with an environment that has pydantic installed.")
    sys.exit(1)

from services.sql_guard import build_analytics_query

def run_test(name: str, spec: dict, expected_fail: bool):
    is_valid, reason, sql, params = build_analytics_query(spec)
    did_fail = not is_valid
    if did_fail == expected_fail:
        print(f"[PASS] {name}")
        return True
    else:
        print(f"[FAIL] {name} | Expected fail: {expected_fail}, Got: {did_fail} | Reason: {reason}")
        return False

tests = [
    {
        "name": "Wrong table/column combination blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "amount"}]},
        "expected_fail": True
    },
    {
        "name": "Direct PII (email) blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "email"}]},
        "expected_fail": True
    },
    {
        "name": "Unknown table blocked",
        "spec": {"tables": ["pg_authid"], "select": [{"table": "pg_authid", "column": "rolname"}]},
        "expected_fail": True
    },
    {
        "name": "Unknown column blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "password_hash"}]},
        "expected_fail": True
    },
    {
        "name": "Dangerous function blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "id", "agg": "pg_sleep"}]},
        "expected_fail": True
    },
    {
        "name": "Malicious operator blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "id"}], "where": [{"table": "customers", "column": "id", "operator": "IN (SELECT pg_sleep(10))", "value": 1}]},
        "expected_fail": True
    },
    {
        "name": "Limit > 100 blocked",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "id"}], "limit": 101},
        "expected_fail": True
    },
    {
        "name": "Invalid spec blocked",
        "spec": {"not_tables": []},
        "expected_fail": True
    },
    {
        "name": "Multiple-statement-style input cannot become executable SQL",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "id"}], "where": [{"table": "customers", "column": "city", "operator": "=", "value": "'; DROP TABLE customers; --"}]},
        "expected_fail": False 
    },
    {
        "name": "Valid customer query allowed",
        "spec": {"tables": ["customers"], "select": [{"table": "customers", "column": "city"}], "limit": 10},
        "expected_fail": False
    },
    {
        "name": "Valid order query allowed",
        "spec": {"tables": ["orders"], "select": [{"table": "orders", "column": "amount", "agg": "SUM"}]},
        "expected_fail": False
    },
    {
        "name": "Valid safe join allowed",
        "spec": {"tables": ["customers", "orders"], "select": [{"table": "customers", "column": "city"}, {"table": "orders", "column": "amount", "agg": "AVG"}]},
        "expected_fail": False
    }
]

def main():
    print("Running Security Regression Tests for NL->SQL boundary...")
    all_passed = True
    for t in tests:
        if not run_test(t["name"], t["spec"], t["expected_fail"]):
            all_passed = False
            
    if all_passed:
        print("All tests passed.")
        sys.exit(0)
    else:
        print("Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
