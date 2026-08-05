/**
 * Determines the health status of a customer.
 * 
 * @param {Object} customer - The customer object.
 * @param {number} customer.total_orders - The total number of orders by the customer.
 * @param {number|string} customer.total_spent - The total amount spent by the customer.
 * @param {number} customer.churn_score - The probability (0-1) that the customer will churn.
 * @returns {string} - The health status ("VIP", "At Risk", or "Active").
 */
export function getCustomerHealth(customer) {
  const totalOrders = Number(customer.total_orders || 0);
  const totalSpent = Number(customer.total_spent || 0);
  
  // High-value, engaged customers are always VIP regardless of base churn risk probability
  if (totalOrders > 4 && totalSpent > 5000) {
    return "VIP";
  }
  
  // For non-VIP, we rely on the backend-computed ML churn score (0-1)
  const churnScore = Number(customer.churn_score || 0);
  
  if (churnScore > 0.70) {
    return "At Risk";
  }
  
  return "Active";
}
