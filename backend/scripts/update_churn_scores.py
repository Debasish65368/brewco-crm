import asyncio
import sys
import os
import pickle
from datetime import datetime

# Add parent directory to path so we can import core.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from core.config import DATABASE_URL
import numpy as np

async def update_scores():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")
        
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    model_path = os.path.join(models_dir, "churn_model.pkl")
    
    if not os.path.exists(model_path):
        raise Exception(f"Model not found at {model_path}. Run train_churn_model.py first.")
        
    with open(model_path, "rb") as f:
        model = pickle.load(f)
        
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Connected to database. Fetching customers...")
        rows = await conn.fetch(
            "SELECT id, total_orders, total_spent, last_order_date FROM customers"
        )
        
        if not rows:
            print("No customers found.")
            return

        now = datetime.now()
        updates = []
        
        for row in rows:
            customer_id = row['id']
            total_orders = float(row['total_orders'] or 0)
            total_spent = float(row['total_spent'] or 0)
            last_order_date = row['last_order_date']
            
            if last_order_date:
                days_since_last_order = (now - last_order_date).days
            else:
                days_since_last_order = 999
                
            avg_order_value = total_spent / total_orders if total_orders > 0 else 0.0
            
            X = np.array([[total_orders, total_spent, days_since_last_order, avg_order_value]])
            
            # predict_proba returns probability for each class, class 1 is churned
            # index 1 gives probability of churning (is_churned=1)
            churn_prob = model.predict_proba(X)[0][1] 
            
            updates.append((churn_prob, customer_id))
            
        print(f"Updating scores for {len(updates)} customers...")
        
        await conn.executemany(
            """
            UPDATE customers
            SET churn_score = $1
            WHERE id = $2
            """,
            updates
        )
        
        print("Update complete!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(update_scores())
