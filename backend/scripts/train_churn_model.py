"""
RETIRED: Supervised Churn Model Training Script.

Fix 3 / Path B Deprecation Notice:
This script previously trained a Logistic Regression classifier on pseudo-labels
derived from a heuristic formula using the exact same input features
(recency, frequency, spend).

Audit Findings:
1. Ground Truth: No independent observed customer churn events, cancellation logs,
   or verified inactivity outcomes exist in the BrewCo dataset.
2. Methodological Defect: Fitting a supervised model on pseudo-labels is circular
   and produces an illusion of statistical learning without true generalization
   or predictive power.
3. Architecture Decision: Fix 3 adopts Path B (Defensible Heuristic Prototype).
   Churn risk is now evaluated transparently and deterministically via
   `backend.services.churn_risk.calculate_churn_risk`, and applied via
   `backend.scripts.update_churn_scores.py`.

This script is preserved for historical reference and documentation integrity,
but will not train or serialize pseudo-label model artifacts.
"""

import sys


def main():
    print("=" * 70)
    print("BREWCO CRM — CHURN MODEL TRAINING RETIRED (FIX 3 / PATH B)")
    print("=" * 70)
    print(
        "Notice: Supervised model training on synthetic pseudo-labels has been retired.\n"
        "Because BrewCo CRM has no independent ground-truth churn outcomes,\n"
        "fitting a classifier to heuristic labels was circular and unvalidated.\n\n"
        "Active Methodology:\n"
        "- Transparent heuristic scoring in `backend/services/churn_risk.py`\n"
        "- Batch database updates in `backend/scripts/update_churn_scores.py`\n"
        "- Scoring: Recency (50%), Frequency (30%), Monetary (20%)\n"
        "- Range: [0.0, 1.0], bounded and deterministic.\n"
    )
    print("No model artifacts were generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
