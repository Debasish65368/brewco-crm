import asyncio
import sys
import os
import pickle
from datetime import datetime

# Add parent directory to path so we can import core.config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg
from core.config import DATABASE_URL
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import numpy as np

async def train_rfm_clusters():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not found")
        
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        print("Connected to database. Fetching customers...")
        rows = await conn.fetch(
            "SELECT id, total_orders, total_spent, last_order_date FROM customers"
        )
        
        features = []
        
        now = datetime.now()
        
        for row in rows:
            total_orders = float(row['total_orders'] or 0)
            total_spent = float(row['total_spent'] or 0)
            last_order_date = row['last_order_date']
            
            # Days since last order (Recency)
            if last_order_date:
                days_since_last_order = (now - last_order_date).days
            else:
                days_since_last_order = 999
                
            features.append([days_since_last_order, total_orders, total_spent])
            
        if not features:
            print("No customers found to train on.")
            return

        print(f"Training on {len(features)} customers...")
        
        X = np.array(features)
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Find best k using silhouette score
        best_k = 2
        best_score = -1
        best_model = None
        
        print("Evaluating k from 2 to 8...")
        for k in range(2, 9):
            # If we have fewer samples than k, break
            if len(X_scaled) <= k:
                break
                
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X_scaled)
            
            # Only compute silhouette if we have >1 cluster and not all points in 1
            if len(np.unique(labels)) > 1:
                score = silhouette_score(X_scaled, labels)
                inertia = kmeans.inertia_
                print(f"k={k}: Silhouette Score = {score:.4f}, Inertia = {inertia:.2f}")
                
                if score > best_score:
                    best_score = score
                    best_k = k
                    best_model = kmeans
        
        if not best_model:
            print("Could not find a valid clustering model.")
            return
            
        print(f"\nSelected best k={best_k} with Silhouette Score={best_score:.4f}")
        
        # Fit final model with best k (already fit in the loop, but we stored it)
        model = best_model
        
        models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        os.makedirs(models_dir, exist_ok=True)
        
        model_path = os.path.join(models_dir, "rfm_model.pkl")
        scaler_path = os.path.join(models_dir, "rfm_scaler.pkl")
        
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
            
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)
            
        print(f"Model trained and saved to {model_path}")
        print(f"Scaler saved to {scaler_path}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(train_rfm_clusters())
