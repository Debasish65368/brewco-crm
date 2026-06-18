import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Mail, MapPin, Search, ShoppingBag, UserRound, WalletCards } from "lucide-react";
import Drawer from "@/components/common/Drawer";
import EmptyState from "@/components/common/EmptyState";
import ErrorState from "@/components/common/ErrorState";
import LoadingSkeleton from "@/components/common/LoadingSkeleton";
import PageHeader from "@/layout/PageHeader";
import { useCustomers } from "@/hooks/useCustomers";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

function formatCurrency(value) {
  return currencyFormatter.format(Number(value || 0));
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(value));
}

function getCustomerHealth(customer) {
  const totalOrders = Number(customer.total_orders || 0);
  const totalSpent = Number(customer.total_spent || 0);

  if (totalOrders > 4 && totalSpent > 5000) {
    return "VIP";
  }

  if (totalOrders === 0) {
    return "At Risk";
  }

  if (customer.last_order_date) {
    const lastOrder = new Date(customer.last_order_date);
    const daysSinceLastOrder = (new Date().getTime() - lastOrder.getTime()) / (1000 * 60 * 60 * 24);

    if (daysSinceLastOrder > 60) {
      return "At Risk";
    }
  }

  return "Active";
}

function HealthBadge({ value }) {
  const styles = {
    VIP: "bg-brew-amber/15 text-brew-roast ring-brew-amber/30",
    "At Risk": "bg-red-100 text-red-800 ring-red-200",
    Active: "bg-green-100 text-green-800 ring-green-200"
  };

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${styles[value]}`}>
      {value}
    </span>
  );
}

function DetailItem({ icon: Icon, label, value, className = "" }) {
  return (
    <div className={`min-w-0 rounded-lg border border-brew-brown/10 bg-brew-cream p-4 ${className}`}>
      <div className="flex items-center gap-2 text-xs font-medium uppercase text-brew-roast">
        <Icon size={15} />
        {label}
      </div>
      <p className="mt-2 break-words text-sm font-semibold text-brew-brown">{value || "Not available"}</p>
    </div>
  );
}

function CustomersPage() {
  const { data, loading, error, refetch } = useCustomers();
  const [search, setSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const lastNoResultQuery = useRef("");

  const filteredCustomers = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) {
      return data;
    }

    return data.filter((customer) =>
      [customer.name, customer.email, customer.city].some((value) =>
        String(value || "").toLowerCase().includes(query)
      )
    );
  }, [data, search]);

  useEffect(() => {
    const query = search.trim();

    if (!query || !data.length || filteredCustomers.length) {
      if (!query) {
        lastNoResultQuery.current = "";
      }
      return;
    }

    if (lastNoResultQuery.current !== query) {
      toast("No customers found for that search");
      lastNoResultQuery.current = query;
    }
  }, [data.length, filteredCustomers.length, search]);

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Customers" description="Search and review BrewCo customer profiles." />
        <LoadingSkeleton rows={5} />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={refetch} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Customers" description="Search and review BrewCo customer profiles." />

      <section className="rounded-lg border border-brew-brown/10 bg-brew-foam p-4 shadow-sm">
        <label className="text-sm font-medium text-brew-brown" htmlFor="customer-search">
          Search customers
        </label>
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-brew-roast" />
          <input
            id="customer-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, email, or city"
            className="h-11 w-full rounded-md border border-brew-brown/15 bg-white pl-10 pr-3 text-sm text-brew-brown outline-none transition placeholder:text-brew-roast/60 focus:border-brew-amber focus:ring-2 focus:ring-brew-amber/20"
          />
        </div>
      </section>

      {!data.length ? (
        <EmptyState
          icon={UserRound}
          title="No customers yet"
          description="Customer records from the backend will appear here once they are available."
        />
      ) : !filteredCustomers.length ? (
        <EmptyState
          icon={Search}
          title="No matching customers"
          description="Try a different name, email, or city search."
        />
      ) : (
        <section className="overflow-hidden rounded-lg border border-brew-brown/10 bg-brew-foam shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-brew-brown/10 text-sm">
              <thead className="bg-brew-cream text-left text-xs uppercase text-brew-roast">
                <tr>
                  <th className="px-4 py-3 font-semibold">Name</th>
                  <th className="px-4 py-3 font-semibold">Email</th>
                  <th className="px-4 py-3 font-semibold">City</th>
                  <th className="px-4 py-3 font-semibold">Health</th>
                  <th className="px-4 py-3 text-right font-semibold">Total Orders</th>
                  <th className="px-4 py-3 text-right font-semibold">Total Spent</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brew-brown/10">
                {filteredCustomers.map((customer) => {
                  const health = getCustomerHealth(customer);
                  const isSelected = String(selectedCustomer?.id) === String(customer.id);

                  return (
                    <tr
                      key={customer.id}
                      onClick={() => setSelectedCustomer(customer)}
                      className={`cursor-pointer transition hover:bg-brew-cream/70 ${isSelected ? "row--selected" : ""}`}
                    >
                      <td className="whitespace-nowrap px-4 py-4 font-medium text-brew-brown">{customer.name}</td>
                      <td className="whitespace-nowrap px-4 py-4 text-brew-roast">{customer.email}</td>
                      <td className="whitespace-nowrap px-4 py-4 text-brew-roast">{customer.city || "Not available"}</td>
                      <td className="whitespace-nowrap px-4 py-4">
                        <HealthBadge value={health} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-right text-brew-brown">
                        {Number(customer.total_orders || 0).toLocaleString("en-US")}
                      </td>
                      <td className="whitespace-nowrap px-4 py-4 text-right font-semibold text-brew-brown">
                        {formatCurrency(customer.total_spent)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <Drawer
        open={Boolean(selectedCustomer)}
        title={selectedCustomer?.name || "Customer details"}
        description={selectedCustomer?.email}
        onClose={() => setSelectedCustomer(null)}
      >
        {selectedCustomer && (
          <div className="space-y-5">
            <div className="rounded-lg border border-brew-brown/10 bg-brew-cream p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <h3 className="break-words text-2xl font-bold text-brew-brown">{selectedCustomer.name}</h3>
                  <p className="mt-1 break-all text-sm text-brew-roast">{selectedCustomer.email}</p>
                  <p className="mt-1 text-sm text-brew-roast">{selectedCustomer.city || "Not available"}</p>
                </div>
                <HealthBadge value={getCustomerHealth(selectedCustomer)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <DetailItem className="col-span-2" icon={Mail} label="Email" value={selectedCustomer.email} />
              <DetailItem icon={MapPin} label="City" value={selectedCustomer.city} />
              <DetailItem icon={ShoppingBag} label="Total orders" value={Number(selectedCustomer.total_orders || 0).toLocaleString("en-US")} />
              <DetailItem icon={WalletCards} label="Total spent" value={formatCurrency(selectedCustomer.total_spent)} />
              <DetailItem icon={UserRound} label="Phone" value={selectedCustomer.phone} />
              <DetailItem icon={ShoppingBag} label="Last order" value={formatDate(selectedCustomer.last_order_date)} />
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}

export default CustomersPage;
