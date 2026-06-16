import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import EmptyState from "@/components/common/EmptyState";

const colors = ["#4a2c1d", "#c8852e", "#6f8068", "#7a5136", "#b42318"];

function CampaignFunnelChart({ stats }) {
  const data = [
    { stage: "Sent", value: stats?.sent ?? 0 },
    { stage: "Delivered", value: stats?.delivered ?? 0 },
    { stage: "Opened", value: stats?.opened ?? 0 },
    { stage: "Clicked", value: stats?.clicked ?? 0 }
  ];

  if (typeof stats?.failed === "number") {
    data.push({ stage: "Failed", value: stats.failed });
  }

  if (!stats || data.every((item) => item.value === 0)) {
    return <EmptyState title="No funnel data" description="Campaign performance stats will appear here when available." />;
  }

  return (
    <div className="h-80 w-full rounded-lg border border-brew-brown/10 bg-brew-foam p-4 shadow-sm">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 12, right: 18, left: 12, bottom: 8 }}>
          <CartesianGrid stroke="#eadfce" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} />
          <YAxis type="category" dataKey="stage" width={84} tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: "rgba(200, 133, 46, 0.10)" }}
            contentStyle={{
              background: "#fffaf3",
              border: "1px solid rgba(74, 44, 29, 0.14)",
              borderRadius: 8,
              color: "#4a2c1d"
            }}
          />
          <Bar dataKey="value" radius={[0, 6, 6, 0]} name="Count">
            {data.map((entry, index) => (
              <Cell key={entry.stage} fill={colors[index % colors.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default CampaignFunnelChart;