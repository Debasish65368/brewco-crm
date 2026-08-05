import asyncio
import sys
import os
import pickle
from datetime import datetime

# Add parent directory to path so we can import core.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from core.config import DATABASE_URL
from sklearn.linear_model import LogisticRegression
import numpy as np

async def train_model():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")
        
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Connected to database. Fetching customers...")
        rows = await conn.fetch(
            "SELECT id, total_orders, total_spent, last_order_date FROM customers"
        )
        
        X = []
        y = []
        
        now = datetime.now()
        
        for row in rows:
            total_orders = float(row['total_orders'] or 0)
            total_spent = float(row['total_spent'] or 0)
            last_order_date = row['last_order_date']
            
            # Days since last order
            if last_order_date:
                days_since_last_order = (now - last_order_date).days
            else:
                # If they never ordered, make it large
                days_since_last_order = 999
                
            # Avg order value (handle div zero)
            avg_order_value = total_spent / total_orders if total_orders > 0 else 0.0
            
            # Composite Risk Score for Label Generation
            recency_risk = min(days_since_last_order / 90.0, 1.0)
            frequency_risk = 1.0 / (1.0 + total_orders)
            monetary_risk = 1.0 / (1.0 + total_spent / 1000.0)
            
            composite_risk = (0.5 * recency_risk) + (0.3 * frequency_risk) + (0.2 * monetary_risk)
            is_churned = 1 if composite_risk > 0.5 else 0
            
            X.append([total_orders, total_spent, days_since_last_order, avg_order_value])
            y.append(is_churned)
            
        if not X:
            print("No customers found to train on.")
            return

        print(f"Training on {len(X)} customers...")
        
        X = np.array(X)
        y = np.array(y)
        
        model = LogisticRegression(max_iter=1000, C=0.1)
        model.fit(X, y)
        
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        os.makedirs(models_dir, exist_ok=True)
        
        model_path = os.path.join(models_dir, "churn_model.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
            
        print(f"Model trained and saved to {model_path}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(train_model())
