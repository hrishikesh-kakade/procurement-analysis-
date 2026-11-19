import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, formatError } from "../api";
import { ANALYTICS, useAuth } from "../auth";
import { money, percent, shortDate } from "../format";
import { useList } from "../hooks";
import { Badge, Card, Empty, ErrorText, PageHeader, Spinner, Stat } from "../ui";

const COLORS = ["#4f46e5", "#0f9d6b", "#e0a21a", "#d64545", "#2b6cb0", "#8b5cf6"];

function AnalyticsDashboard() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get("/analytics/total-spend"),
      api.get("/analytics/average-po"),
      api.get("/analytics/rejection-rate"),
      api.get("/analytics/monthly-spend"),
      api.get("/analytics/department-spend"),
      api.get("/analytics/supplier-scorecard"),
    ])
      .then(([spend, avg, rejection, monthly, departments, scorecard]) =>
        setData({ spend, avg, rejection, monthly, departments, scorecard }),
      )
      .catch((e) => setError(formatError(e)));
  }, []);

  if (error) return <ErrorText error={error} />;
  if (!data) return <Spinner />;
  return (
    <>
      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <Stat label="Total spend" value={money(data.spend.total_spend)} hint="Issued and received orders" />
        <Stat label="Orders" value={data.spend.order_count} />
        <Stat label="Average order" value={money(data.avg.average_po_value)} />
        <Stat label="Requisition rejection rate" value={percent(data.rejection.rejection_rate_percent)} hint={`${data.rejection.rejected_count} of ${data.rejection.decided_count} decided`} />
      </div>
      <div className="grid cols-2">
        <Card title="Monthly spend">
          {data.monthly.length === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.monthly.map((m: any) => ({ ...m, total_spend: Number(m.total_spend) }))}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}k` : v)} />
                <Tooltip formatter={(v: any) => money(v)} />
                <Bar dataKey="total_spend" fill="#4f46e5" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card title="Spend by department">
          {data.departments.length === 0 ? <Empty /> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={data.departments.map((d: any) => ({ ...d, total_spend: Number(d.total_spend) }))} dataKey="total_spend" nameKey="department" outerRadius={95} innerRadius={50} paddingAngle={2}>
                  {data.departments.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(v: any) => money(v)} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
      <Card title="Supplier scorecard">
        {data.scorecard.length === 0 ? <Empty /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Supplier</th><th className="num">Orders</th><th className="num">Spend</th><th className="num">Fulfilment</th><th className="num">On-time</th><th className="num">Score</th><th>Rating</th></tr></thead>
              <tbody>
                {data.scorecard.slice(0, 8).map((s: any) => (
                  <tr key={s.supplier_id}>
                    <td>{s.supplier_name}</td><td className="num">{s.order_count}</td><td className="num">{money(s.total_spend)}</td>
                    <td className="num">{percent(s.fulfillment_rate_percent)}</td><td className="num">{percent(s.on_time_delivery_rate_percent)}</td>
                    <td className="num">{s.score ?? "—"}</td><td><Badge value={s.rating} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

function RequesterDashboard() {
  const { data, loading, error } = useList("/requisitions", { limit: 8 });
  return (
    <Card title="Recent requisitions">
      <ErrorText error={error} />
      {loading ? <Spinner /> : !data?.items.length ? <Empty text="No requisitions yet — create one from the Requisitions page." /> : (
        <table>
          <thead><tr><th>Number</th><th>Department</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            {data.items.map((r: any) => (
              <tr key={r.id}><td>{r.requisition_number}</td><td>{r.department}</td><td><Badge value={r.status} /></td><td>{shortDate(r.created_at)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export default function Dashboard() {
  const { user, can } = useAuth();
  return (
    <>
      <PageHeader title={`Welcome back, ${user?.full_name?.split(" ")[0]}`} subtitle="Here is what is happening across procurement." />
      {can(...ANALYTICS) ? <AnalyticsDashboard /> : <RequesterDashboard />}
    </>
  );
}
