import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import EmptyState from "@/components/common/EmptyState";

function CityCustomersBarChart({ data = [] }) {
  if (!data.length) {
    return <EmptyState title="No city data" description="Customer city totals will appear once customer records are available." />;
  }

  return (
    <div className="h-80 w-full rounded-lg border border-brew-brown/10 bg-brew-foam p-4 shadow-sm">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid stroke="#eadfce" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="city" tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "#7a5136", fontSize: 12 }} />
          <Tooltip
            cursor={{ fill: "rgba(200, 133, 46, 0.10)" }}
            contentStyle={{
              background: "#fffaf3",
              border: "1px solid rgba(74, 44, 29, 0.14)",
              borderRadius: 8,
              color: "#4a2c1d"
            }}
          />
          <Bar dataKey="customers" fill="#c8852e" radius={[6, 6, 0, 0]} name="Customers" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default CityCustomersBarChart;