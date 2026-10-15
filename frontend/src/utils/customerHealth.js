/**
 * Determines the health tier of a customer for CRM workflows.
 *
 * Risk categories:
 * - "VIP": High-value, engaged customers (orders > 4 and spent > ₹5,000),
 *   prioritized for loyalty regardless of baseline recency scores.
 * - "At Risk": Customers whose heuristic churn-risk score exceeds 0.70,
 *   indicating extended dormancy and low habituation.
 * - "Active": Customers with current engagement and churn-risk score <= 0.70.
 * - "Unscored": Customers with no order history or missing churn score data,
 *   preventing unverified data from being presented as low churn risk.
 *
 * Note: The underlying churn_score is a heuristic behavioral index (0.0 to 1.0),
 * not an empirically validated or calibrated probability of churn.
 *
 * @param {Object} customer - The customer object.
 * @param {number} [customer.total_orders] - The total number of orders by the customer.
 * @param {number|string} [customer.total_spent] - The total amount spent by the customer.
 * @param {number|null} [customer.churn_score] - Heuristic risk score (0.0 to 1.0).
 * @returns {string} - The health status ("VIP", "At Risk", "Active", or "Unscored").
 */
export function getCustomerHealth(customer) {
  if (!customer) {
    return "Unscored";
  }

  const totalOrders = Number(customer.total_orders || 0);
  const totalSpent = Number(customer.total_spent || 0);

  // High-value, engaged customers are always VIP regardless of baseline churn risk score
  if (totalOrders > 4 && totalSpent > 5000) {
    return "VIP";
  }

  // Customers with zero orders have no transaction history to assess for churn
  if (totalOrders === 0) {
    return "Unscored";
  }

  // Explicitly handle missing or uncalculated churn score:
  // Missing data is not presented as reliable evidence of low churn risk.
  if (
    customer.churn_score === null ||
    customer.churn_score === undefined ||
    customer.churn_score === "" ||
    isNaN(Number(customer.churn_score))
  ) {
    return "Unscored";
  }

  const churnScore = Number(customer.churn_score);

  // Documented threshold: scores above 0.70 indicate high dormancy / churn risk
  if (churnScore > 0.70) {
    return "At Risk";
  }

  return "Active";
}
