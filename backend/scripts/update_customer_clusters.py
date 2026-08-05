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

async def update_clusters():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")
        
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    model_path = os.path.join(models_dir, "rfm_model.pkl")
    scaler_path = os.path.join(models_dir, "rfm_scaler.pkl")
    
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        raise Exception(f"Model or scaler not found in {models_dir}. Run train_rfm_clusters.py first.")
        
    with open(model_path, "rb") as f:
        model = pickle.load(f)
        
    with open(scaler_path, "rb") as f:
        scaler = pickle.load(f)
        
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
        features_batch = []
        customer_ids = []
        
        for row in rows:
            customer_id = row['id']
            total_orders = float(row['total_orders'] or 0)
            total_spent = float(row['total_spent'] or 0)
            last_order_date = row['last_order_date']
            
            if last_order_date:
                days_since_last_order = (now - last_order_date).days
            else:
                days_since_last_order = 999
                
            features_batch.append([days_since_last_order, total_orders, total_spent])
            customer_ids.append(customer_id)
            
        X = np.array(features_batch)
        X_scaled = scaler.transform(X)
        
        cluster_labels = model.predict(X_scaled)
        
        for i in range(len(customer_ids)):
            # convert np.int32 to native int for asyncpg
            cluster_id = int(cluster_labels[i])
            updates.append((cluster_id, customer_ids[i]))
            
        print(f"Updating cluster_id for {len(updates)} customers...")
        
        await conn.executemany(
            """
            UPDATE customers
            SET cluster_id = $1
            WHERE id = $2
            """,
            updates
        )
        
        print("Update complete!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(update_clusters())
