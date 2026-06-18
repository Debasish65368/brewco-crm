import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  CalendarClock,
  MailCheck,
  MousePointerClick,
  PackageCheck,
  ReceiptText,
  Send,
  Star,
  TrendingUp,
  Users
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import CityCustomersBarChart from "@/components/charts/CityCustomersBarChart";
import EmptyState from "@/components/common/EmptyState";
import ErrorState from "@/components/common/ErrorState";
import LoadingSkeleton from "@/components/common/LoadingSkeleton";
import MetricCard from "@/components/common/MetricCard";
import PageHeader from "@/layout/PageHeader";
import { useCustomers } from "@/hooks/useCustomers";
import { useDashboard } from "@/hooks/useDashboard";
import { getRevenueTrend } from "@/services/dashboardApi";

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatCurrency(value) {
  return currencyFormatter.format(Number(value || 0));
}

function formatRate(value) {
  const number = Number(value || 0);
  return `${number.toFixed(number % 1 === 0 ? 0 : 1)}%`;
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric"
  }).format(new Date(value));
}

function useCountUp(value, { duration = 850, formatter = formatNumber } = {}) {
  const [displayValue, setDisplayValue] = useState(formatter(0));

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const target = Number(value || 0);

    if (mediaQuery.matches) {
      setDisplayValue(formatter(target));
      return undefined;
    }

    let frameId;
    const start = performance.now();

    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(formatter(target * eased));

      if (progress < 1) {
        frameId = requestAnimationFrame(tick);
      }
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [duration, formatter, value]);

  return displayValue;
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

function getInitials(name = "") {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function AnimatedMetricCard({ metric, index }) {
  const animatedValue = useCountUp(metric.rawValue, {
    formatter: metric.formatter || formatNumber
  });

  return (
    <div className="dashboard-enter" style={{ animationDelay: `${index * 70}ms` }}>
      <MetricCard {...metric} value={animatedValue} />
    </div>
  );
}

function SectionCard({ title, icon: Icon, children, className = "", bodyClassName = "", delay = 0 }) {
  return (
    <section
      className={`dashboard-enter dashboard-hover rounded-lg border border-brew-brown/10 bg-brew-foam p-5 shadow-sm ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="mb-4 flex items-center gap-2">
        {Icon && <Icon className="h-5 w-5 text-brew-amber" />}
        <h2 className="text-base font-semibold text-brew-brown">{title}</h2>
      </div>
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

function RevenueTrendChart({ data = [] }) {
  if (!data.length || data.every((item) => Number(item.revenue || 0) === 0)) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No revenue trend yet"
        description="Revenue by day will appear after orders are recorded in the last 30 days."
      />
    );
  }

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 14, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#eadfce" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatDate} tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} />
          <YAxis tickFormatter={(value) => `$${Number(value).toLocaleString("en-US")}`} tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} width={74} />
          <Tooltip
            labelFormatter={(label) => formatDate(label)}
            formatter={(value) => [formatCurrency(value), "Revenue"]}
            contentStyle={{ background: "#fffaf3", border: "1px solid rgba(74, 44, 29, 0.14)", borderRadius: 8, color: "#4a2c1d" }}
          />
          <Line type="monotone" dataKey="revenue" stroke="#c8852e" strokeWidth={3} dot={false} activeDot={{ r: 5, fill: "#4a2c1d", stroke: "#c8852e", strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function FunnelStage({ label, value, max, delay }) {
  const width = max > 0 ? Math.max(4, Math.min(100, (Number(value || 0) / max) * 100)) : 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-brew-brown">{label}</span>
        <span className="text-brew-roast">{formatNumber(value)}</span>
      </div>
      <div className="h-4 overflow-hidden rounded-full bg-brew-brown/10">
        <div
          className="h-full rounded-full bg-brew-amber transition-[width] duration-700 ease-out motion-reduce:transition-none"
          style={{ width: `${width}%`, transitionDelay: `${delay}ms` }}
        />
      </div>
    </div>
  );
}

function ConversionLabel({ from, to, fromValue, toValue }) {
  const rate = Number(fromValue || 0) > 0 ? (Number(toValue || 0) / Number(fromValue || 0)) * 100 : 0;

  return (
    <div className="rounded-full bg-brew-cream px-3 py-1 text-xs font-medium text-brew-roast ring-1 ring-brew-brown/10">
      {from} to {to}: {formatRate(rate)}
    </div>
  );
}

function CampaignFunnelAnchor({ stats }) {
  const sent = Number(stats.sent || 0);

  if (!sent) {
    return <EmptyState icon={BarChart3} title="No funnel data" description="Campaign performance appears after campaigns send messages." />;
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-2 sm:grid-cols-3">
        <ConversionLabel from="Sent" to="Delivered" fromValue={stats.sent} toValue={stats.delivered} />
        <ConversionLabel from="Delivered" to="Opened" fromValue={stats.delivered} toValue={stats.opened} />
        <ConversionLabel from="Opened" to="Clicked" fromValue={stats.opened} toValue={stats.clicked} />
      </div>
      <div className="space-y-5">
        <FunnelStage label="Sent" value={stats.sent} max={sent} delay={0} />
        <FunnelStage label="Delivered" value={stats.delivered} max={sent} delay={80} />
        <FunnelStage label="Opened" value={stats.opened} max={sent} delay={160} />
        <FunnelStage label="Clicked" value={stats.clicked} max={sent} delay={240} />
      </div>
    </div>
  );
}

function DashboardPage() {
  const { data, loading, error, refetch } = useDashboard();
  const { data: customers, loading: customersLoading, error: customersError, refetch: refetchCustomers } = useCustomers();
  const [revenueTrend, setRevenueTrend] = useState([]);
  const [revenueLoading, setRevenueLoading] = useState(true);
  const [revenueError, setRevenueError] = useState(null);
  const [selectedTopCustomerId, setSelectedTopCustomerId] = useState(null);
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [selectedReviewId, setSelectedReviewId] = useState(null);

  const fetchRevenueTrend = async () => {
    setRevenueLoading(true);
    setRevenueError(null);

    try {
      const result = await getRevenueTrend();
      setRevenueTrend(Array.isArray(result) ? result : []);
    } catch (err) {
      setRevenueError(err.message);
    } finally {
      setRevenueLoading(false);
    }
  };

  useEffect(() => {
    fetchRevenueTrend();
  }, []);

  const cityChartData = useMemo(() => {
    const cityCounts = customers.reduce((acc, customer) => {
      const city = customer.city || "Unknown";
      acc[city] = (acc[city] || 0) + 1;
      return acc;
    }, {});

    return Object.entries(cityCounts)
      .map(([city, count]) => ({ city, customers: count }))
      .sort((a, b) => b.customers - a.customers)
      .slice(0, 8);
  }, [customers]);

  const citySummary = useMemo(() => {
    const largest = cityChartData[0];
    const totalCustomers = cityChartData.reduce((sum, item) => sum + item.customers, 0);

    return {
      totalCities: cityChartData.length,
      largestCity: largest ? `${largest.city} (${largest.customers})` : "Not available",
      totalCustomers
    };
  }, [cityChartData]);

  const topCustomers = useMemo(() => [...customers].sort((a, b) => Number(b.total_spent || 0) - Number(a.total_spent || 0)).slice(0, 10), [customers]);

  const customerReviews = useMemo(() => {
    const quotes = [
      "Best coffee subscription I have tried. The deliveries are quick and the roast is always fresh.",
      "BrewCo makes it easy to keep my pantry stocked. The flavor has been consistent every single order.",
      "The recommendations are spot on, and the checkout experience feels effortless.",
      "Reliable service, warm packaging, and coffee that tastes like it was packed the same morning.",
      "Every blend feels thoughtfully chosen. It has become part of my morning routine.",
      "The seasonal offers are genuinely useful, and the coffee arrives right when expected.",
      "Great aroma, smooth roast, and customer support that actually feels personal.",
      "The beans are consistently fresh, and the ordering experience is refreshingly simple.",
      "I like how easy it is to discover new roasts without losing my usual favorites.",
      "Fast delivery, rich flavor, and packaging that feels premium without being wasteful."
    ];
    const ratings = [5, 5, 4, 5, 5, 4, 5, 5, 4, 5];
    const avatarStyles = [
      "bg-brew-brown text-brew-foam",
      "bg-brew-amber text-white",
      "bg-brew-sage text-white",
      "bg-brew-roast text-brew-foam",
      "bg-brew-caramel text-brew-brown",
      "bg-brew-espresso text-brew-foam",
      "bg-brew-brown/80 text-brew-foam",
      "bg-brew-amber/80 text-white",
      "bg-brew-sage/80 text-white",
      "bg-brew-roast/80 text-brew-foam"
    ];

    return topCustomers.slice(0, 10).map((customer, index) => ({
      id: customer.id,
      name: customer.name,
      quote: quotes[index],
      rating: ratings[index],
      initials: getInitials(customer.name),
      avatarClassName: avatarStyles[index]
    }));
  }, [topCustomers]);

  const recentActivity = useMemo(() => {
    const activity = [];
    const sent = Number(data?.sent || 0);
    const delivered = Number(data?.delivered || 0);
    const deliveryRate = sent > 0 ? (delivered / sent) * 100 : 0;

    if (sent > 0) {
      activity.push({ id: "delivery-summary", label: "Campaign delivery", meta: `Sent to ${formatNumber(sent)} customers · ${formatRate(deliveryRate)} delivered`, type: "Campaign", date: data?.recent_campaigns?.[0]?.created_at });
    }

    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const newThisWeek = customers.filter((customer) => customer.created_at && new Date(customer.created_at) >= oneWeekAgo).length;

    if (newThisWeek > 0) {
      activity.push({ id: "new-customers-week", label: "New customers", meta: `${formatNumber(newThisWeek)} new customers joined this week`, type: "Customers", date: new Date().toISOString() });
    }

    (data?.recent_campaigns || []).slice(0, 3).forEach((campaign) => {
      activity.push({ id: `campaign-${campaign.id}`, label: campaign.name, meta: `${campaign.channel || "Campaign"} campaign · ${campaign.status || "status unavailable"}`, type: "Campaign", date: campaign.created_at });
    });

    return activity.sort((a, b) => new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime()).slice(0, 5);
  }, [customers, data]);

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
    return <EmptyState icon={BarChart3} title="No dashboard data" description="Dashboard stats will appear once the backend returns data." />;
  }

  const metricCards = [
    { title: "Customers", rawValue: data.total_customers, description: "Total customer profiles", icon: Users, tone: "brown" },
    { title: "Orders", rawValue: data.total_orders, description: "Orders tracked in CRM", icon: ReceiptText, tone: "amber" },
    { title: "Revenue", rawValue: data.total_revenue, formatter: formatCurrency, description: "Total attributed revenue", icon: PackageCheck, tone: "sage" },
    { title: "Campaigns", rawValue: data.total_campaigns, description: "Campaigns created", icon: Send, tone: "brown" },
    { title: "Delivery rate", rawValue: data.delivery_rate, formatter: formatRate, description: `${formatNumber(data.delivered)} delivered of ${formatNumber(data.sent)} sent`, icon: MailCheck, tone: "sage" },
    { title: "Open rate", rawValue: data.open_rate, formatter: formatRate, description: `${formatNumber(data.opened)} opens recorded`, icon: BarChart3, tone: "amber" },
    { title: "Click rate", rawValue: data.click_rate, formatter: formatRate, description: `${formatNumber(data.clicked)} clicks recorded`, icon: MousePointerClick, tone: "sage" }
  ];

  const funnelStats = { sent: data.sent, delivered: data.delivered, opened: data.opened, clicked: data.clicked };

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="A quick read on BrewCo customer growth and campaign performance." />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((metric, index) => <AnimatedMetricCard key={metric.title} metric={metric} index={index} />)}
      </section>

      <section className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <SectionCard title="Customers by city" icon={Users} className="xl:col-span-6" delay={120}>
          {customersLoading ? <LoadingSkeleton rows={3} /> : customersError ? <ErrorState message={customersError} onRetry={refetchCustomers} /> : cityChartData.length ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg bg-brew-cream p-3 ring-1 ring-brew-brown/10"><p className="text-xs text-brew-roast">Total Cities</p><p className="mt-1 text-lg font-semibold text-brew-brown">{formatNumber(citySummary.totalCities)}</p></div>
                <div className="rounded-lg bg-brew-cream p-3 ring-1 ring-brew-brown/10"><p className="text-xs text-brew-roast">Largest City</p><p className="mt-1 truncate text-lg font-semibold text-brew-brown">{citySummary.largestCity}</p></div>
                <div className="rounded-lg bg-brew-cream p-3 ring-1 ring-brew-brown/10"><p className="text-xs text-brew-roast">Represented</p><p className="mt-1 text-lg font-semibold text-brew-brown">{formatNumber(citySummary.totalCustomers)}</p></div>
              </div>
              <CityCustomersBarChart data={cityChartData} />
            </div>
          ) : <EmptyState icon={Users} title="No city data" description="Customer city totals will appear once customers are available." />}
        </SectionCard>

        <SectionCard title="Revenue trend" icon={TrendingUp} className="xl:col-span-6" delay={180}>
          {revenueLoading ? <LoadingSkeleton rows={3} /> : revenueError ? <ErrorState message={revenueError} onRetry={fetchRevenueTrend} /> : <RevenueTrendChart data={revenueTrend} />}
        </SectionCard>
      </section>

      <section className="grid grid-cols-1 items-start gap-5 xl:grid-cols-12">
        <div className="grid gap-5 xl:col-span-7">
          <SectionCard title="Campaign funnel" icon={BarChart3} className="self-start" bodyClassName="pb-0" delay={240}>
            <CampaignFunnelAnchor stats={funnelStats} />
          </SectionCard>

          <SectionCard title="Customer reviews" icon={Star} delay={300}>
            {customersLoading ? <LoadingSkeleton rows={4} /> : customerReviews.length ? (
              <div className="scroll-container max-h-[482px] overflow-x-hidden overflow-y-auto pr-2 scroll-smooth">
                <div className="grid gap-3 sm:grid-cols-2">
                  {customerReviews.map((review) => {
                    const isSelected = selectedReviewId === review.id;

                    return (
                      <button
                        key={review.id}
                        type="button"
                        onClick={() => setSelectedReviewId(review.id)}
                        className={`min-h-[146px] rounded-lg border bg-brew-cream p-3 text-left transition duration-200 ease-out hover:border-brew-amber/40 hover:bg-white hover:shadow-sm ${
                          isSelected ? "row--selected shadow-md" : "border-brew-brown/10 shadow-none"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-semibold ${review.avatarClassName}`}>
                            {review.initials}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-semibold text-brew-brown">{review.name}</p>
                            <div className="mt-1 flex items-center gap-0.5 text-brew-amber">
                              {Array.from({ length: 5 }).map((_, index) => (
                                <Star
                                  key={index}
                                  size={13}
                                  className={index < review.rating ? "fill-current" : "text-brew-brown/20"}
                                />
                              ))}
                            </div>
                          </div>
                        </div>
                        <p className="mt-3 text-sm leading-5 text-brew-roast">"{review.quote}"</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : (
              <EmptyState icon={Star} title="No customer reviews yet" description="Reviews will use top customer names when customer data is available." />
            )}
          </SectionCard>
        </div>

        <div className="grid gap-5 xl:col-span-5">
          <SectionCard title="Top customers" icon={PackageCheck} delay={300}>
            {customersLoading ? <LoadingSkeleton rows={5} /> : customersError ? <ErrorState message={customersError} onRetry={refetchCustomers} /> : topCustomers.length ? (
              <div className="space-y-2">
                <div className="grid grid-cols-[32px_minmax(0,1fr)_82px_92px_78px] gap-2 px-2 text-xs font-semibold uppercase text-brew-roast">
                  <span>Rank</span><span>Name</span><span>Orders</span><span>Spent</span><span>Health</span>
                </div>
                <div className="scroll-container max-h-[292px] space-y-2 overflow-x-hidden overflow-y-auto pr-2 scroll-smooth">
                  {topCustomers.map((customer, index) => {
                    const health = getCustomerHealth(customer);
                    const isSelected = selectedTopCustomerId === customer.id;

                    return (
                      <button
                        key={customer.id}
                        type="button"
                        onClick={() => setSelectedTopCustomerId(customer.id)}
                        className={`grid w-full grid-cols-[32px_minmax(0,1fr)_82px_92px_78px] items-center gap-2 rounded-lg border bg-brew-cream px-2 py-2 text-left text-sm transition duration-200 ease-out hover:border-brew-amber/40 hover:bg-white hover:shadow-sm ${
                          isSelected ? "row--selected shadow-md" : "border-brew-brown/10 shadow-none"
                        }`}
                      >
                        <span className="font-semibold text-brew-brown">{index + 1}</span>
                        <span className="min-w-0"><span className="block truncate font-semibold text-brew-brown">{customer.name}</span><span className="block truncate text-xs text-brew-roast">{customer.city || "Unknown city"}</span></span>
                        <span className="text-brew-roast">{formatNumber(customer.total_orders)}</span>
                        <span className="font-semibold text-brew-brown">{formatCurrency(customer.total_spent)}</span>
                        <HealthBadge value={health} />
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : <EmptyState icon={Users} title="No top customers yet" description="Top spenders will appear when customer spend data is available." />}
          </SectionCard>

          <SectionCard title="Recent activity" icon={Activity} delay={360}>
            {customersLoading ? <LoadingSkeleton rows={4} /> : recentActivity.length ? (
              <div className="space-y-2">
                {recentActivity.map((activity, index) => (
                  <button
                    key={activity.id}
                    type="button"
                    onClick={() => setSelectedActivityId(activity.id)}
                    className={`dashboard-enter flex w-full items-start gap-3 rounded-lg border bg-brew-cream p-3 text-left transition duration-200 ease-out hover:border-brew-amber/40 hover:bg-white hover:shadow-sm ${
                      selectedActivityId === activity.id ? "row--selected shadow-md" : "border-brew-brown/10 shadow-none"
                    }`}
                    style={{ animationDelay: `${420 + index * 80}ms` }}
                  >
                    <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brew-amber/15 text-brew-amber"><CalendarClock size={17} /></div>
                    <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-sm font-semibold text-brew-brown">{activity.label}</p><span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-brew-roast ring-1 ring-brew-brown/10">{activity.type}</span></div><p className="mt-1 text-sm text-brew-roast">{activity.meta}</p><p className="mt-1 text-xs text-brew-roast/75">{formatDate(activity.date)}</p></div>
                  </button>
                ))}
              </div>
            ) : <EmptyState icon={Activity} title="No recent activity available" description="The current customer and campaign records do not expose enough dated activity yet." />}
          </SectionCard>

        </div>
      </section>
    </div>
  );
}

export default DashboardPage;
