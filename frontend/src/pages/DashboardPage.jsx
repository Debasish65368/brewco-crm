import { BarChart3, MailCheck, MousePointerClick, PackageCheck, ReceiptText, Send, Users } from "lucide-react";
import CampaignFunnelChart from "@/components/charts/CampaignFunnelChart";
import CityCustomersBarChart from "@/components/charts/CityCustomersBarChart";
import EmptyState from "@/components/common/EmptyState";
import ErrorState from "@/components/common/ErrorState";
import LoadingSkeleton from "@/components/common/LoadingSkeleton";
import MetricCard from "@/components/common/MetricCard";
import PageHeader from "@/layout/PageHeader";
import { useDashboard } from "@/hooks/useDashboard";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatRate(value) {
  const number = Number(value || 0);
  return `${number.toFixed(number % 1 === 0 ? 0 : 1)}%`;
}

function getCityChartData(data) {
  const source = data?.customers_by_city || data?.city_customers || data?.customer_city_counts || [];

  if (!Array.isArray(source)) {
    return [];
  }

  return source
    .map((item) => ({
      city: item.city || item.name || "Unknown",
      customers: Number(item.customers ?? item.count ?? item.total ?? 0)
    }))
    .filter((item) => item.customers > 0);
}

function DashboardPage() {
  const { data, loading, error, refetch } = useDashboard();

  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="Dashboard" description="A quick read on BrewCo customer growth and campaign performance." />
        <LoadingSkeleton variant="cards" rows={4} />
        <LoadingSkeleton rows={2} />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={refetch} />;
  }

  if (!data) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No dashboard data"
        description="Dashboard stats will appear once the backend returns data."
      />
    );
  }

  const metricCards = [
    {
      title: "Customers",
      value: formatNumber(data.total_customers),
      description: "Total customer profiles",
      icon: Users,
      tone: "brown"
    },
    {
      title: "Orders",
      value: formatNumber(data.total_orders),
      description: "Orders tracked in CRM",
      icon: ReceiptText,
      tone: "amber"
    },
    {
      title: "Revenue",
      value: currencyFormatter.format(Number(data.total_revenue || 0)),
      description: "Total attributed revenue",
      icon: PackageCheck,
      tone: "sage"
    },
    {
      title: "Campaigns",
      value: formatNumber(data.total_campaigns),
      description: "Campaigns created",
      icon: Send,
      tone: "brown"
    },
    {
      title: "Delivery rate",
      value: formatRate(data.delivery_rate),
      description: `${formatNumber(data.delivered)} delivered of ${formatNumber(data.sent)} sent`,
      icon: MailCheck,
      tone: "sage"
    },
    {
      title: "Open rate",
      value: formatRate(data.open_rate),
      description: `${formatNumber(data.opened)} opens recorded`,
      icon: BarChart3,
      tone: "amber"
    },
    {
      title: "Click rate",
      value: formatRate(data.click_rate),
      description: `${formatNumber(data.clicked)} clicks recorded`,
      icon: MousePointerClick,
      tone: "sage"
    }
  ];

  const funnelStats = {
    sent: data.sent,
    delivered: data.delivered,
    opened: data.opened,
    clicked: data.clicked
  };
  const cityChartData = getCityChartData(data);

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="A quick read on BrewCo customer growth and campaign performance." />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((metric) => (
          <MetricCard key={metric.title} {...metric} />
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-brew-brown">Customers by city</h2>
          {cityChartData.length ? (
            <CityCustomersBarChart data={cityChartData} />
          ) : (
            <EmptyState
              icon={Users}
              title="No city breakdown available"
              description="The dashboard stats response does not include city-grouped customer data yet."
            />
          )}
        </div>

        <div className="space-y-3">
          <h2 className="text-base font-semibold text-brew-brown">Campaign funnel</h2>
          <CampaignFunnelChart stats={funnelStats} />
        </div>
      </section>
    </div>
  );
}

export default DashboardPage;