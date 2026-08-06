import re

ALLOWED_TABLES = {"customers", "orders", "segments", "campaigns", "communications"}
FORBIDDEN_KEYWORDS = {"insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "exec"}

def validate_sql(sql: str) -> tuple[bool, str]:
    """Validates the generated SQL for safety and constraints."""
    sql_upper = sql.upper().strip()
    
    # 1. Starts with SELECT
    if not sql_upper.startswith("SELECT"):
        return False, "Query must start with SELECT"
        
    # 2. No semicolons
    if ";" in sql:
        return False, "Semicolons are not allowed"
        
    # 3. No forbidden keywords
    words = re.findall(r'\b\w+\b', sql_upper)
    for word in words:
        if word in FORBIDDEN_KEYWORDS:
            return False, f"Forbidden keyword found: {word}"
            
    # 4. Check tables referenced in FROM or JOIN
    table_pattern = re.compile(r'\b(?:FROM|JOIN)\s+([a-zA-Z0-9_"\.]+)', re.IGNORECASE)
    matches = table_pattern.findall(sql)
    
    if not matches:
        return False, "No tables found in FROM or JOIN clauses"
        
    for match in matches:
        clean_table = match.replace('"', '').split('.')[-1].lower()
        if clean_table not in ALLOWED_TABLES:
            return False, f"Table not allowed: {clean_table}"
            
    # 5. Does not select email or phone columns directly or use SELECT *
    select_clause_match = re.search(r'^SELECT\s+(.*?)\s+(?:FROM|WHERE|GROUP|ORDER|LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)
    if select_clause_match:
        select_clause = select_clause_match.group(1).lower()
        
        # Prevent SELECT *
        select_clause_no_count = re.sub(r'count\s*\(\s*\*\s*\)', '', select_clause, flags=re.IGNORECASE)
        if '*' in select_clause_no_count:
            return False, "Using '*' is not allowed. All columns must be explicitly specified."
            
        if re.search(r'\b(email|phone)\b', select_clause):
            # Allow them strictly inside an aggregate function
            if not re.search(r'(count|sum|avg|max|min)\s*\([^)]*\b(email|phone)\b[^)]*\)', select_clause):
                return False, "Selecting email or phone columns directly is not allowed"

    return True, "Valid SQL"
