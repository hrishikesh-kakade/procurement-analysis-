import { useEffect, useState } from "react";
import { api, formatError } from "../api";
import { MANAGE, useAuth } from "../auth";
import { money, shortDate } from "../format";
import { useList, useLookup } from "../hooks";
import { Badge, Card, Empty, ErrorText, Modal, PageHeader, Pagination, Spinner, useToast } from "../ui";

function Detail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const [po, setPo] = useState<any>(null);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [qty, setQty] = useState<Record<number, string>>({});
  const { names: suppliers } = useLookup("/suppliers");
  const { names: materials } = useLookup("/materials");
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setPo(await api.get(`/purchase-orders/${id}`));
      setDeliveries(await api.get(`/purchase-orders/${id}/deliveries`));
    } catch (e) {
      setError(formatError(e));
    }
  };
  useEffect(() => { load(); }, [id]);

  async function act(message: string, call: () => Promise<any>) {
    try {
      await call();
      toast(message);
      setQty({});
      await load();
      onChanged();
    } catch (e) {
      toast(formatError(e), "err");
    }
  }

  if (error) return <Modal title="Purchase order" onClose={onClose}><ErrorText error={error} /></Modal>;
  if (!po) return <Modal title="Purchase order" onClose={onClose}><Spinner /></Modal>;

  const canManage = can(...MANAGE);
  const receivable = ["issued", "partially_received"].includes(po.status);
  const lines = po.items.filter((i: any) => Number(qty[i.id]) > 0).map((i: any) => ({ po_item_id: i.id, quantity_received: Number(qty[i.id]) }));

  return (
    <Modal title={po.po_number} onClose={onClose} wide>
      <div className="row" style={{ marginBottom: 14 }}><Badge value={po.status} /><span className="muted">Ordered {shortDate(po.order_date)} · Expected {shortDate(po.expected_delivery_date)}</span></div>
      <dl className="kv">
        <dt>Supplier</dt><dd>{suppliers[po.supplier_id] ?? `#${po.supplier_id}`}</dd>
        <dt>Total</dt><dd><strong>{money(po.total_amount)}</strong> <span className="muted">(calculated by the server)</span></dd>
        {po.notes && (<><dt>Notes</dt><dd>{po.notes}</dd></>)}
      </dl>
      <table>
        <thead><tr><th>Material</th><th className="num">Ordered</th><th className="num">Received</th><th className="num">Unit price</th><th className="num">Line total</th>{canManage && receivable && <th className="num">Receive now</th>}</tr></thead>
        <tbody>
          {po.items.map((i: any) => (
            <tr key={i.id}>
              <td>{materials[i.material_id] ?? `#${i.material_id}`}</td><td className="num">{i.quantity}</td><td className="num">{i.received_quantity}</td>
              <td className="num">{money(i.unit_price)}</td><td className="num">{money(i.line_total)}</td>
              {canManage && receivable && (
                <td className="num"><input type="number" min={0} max={i.quantity - i.received_quantity} style={{ width: 90 }} value={qty[i.id] ?? ""} onChange={(e) => setQty({ ...qty, [i.id]: e.target.value })} disabled={i.quantity === i.received_quantity} /></td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {canManage && (
        <div className="row" style={{ marginTop: 18 }}>
          {po.status === "draft" && <button className="btn" onClick={() => act("Order issued", () => api.patch(`/purchase-orders/${id}/status`, { status: "issued" }))}>Issue order</button>}
          {["draft", "issued"].includes(po.status) && <button className="btn ghost" onClick={() => window.confirm("Cancel this order?") && act("Order cancelled", () => api.patch(`/purchase-orders/${id}/status`, { status: "cancelled" }))}>Cancel order</button>}
          {receivable && <button className="btn success" disabled={!lines.length} onClick={() => act("Delivery recorded", () => api.post(`/purchase-orders/${id}/deliveries`, { items: lines }))}>Record delivery</button>}
        </div>
      )}

      <div className="section-title">Deliveries</div>
      {deliveries.length === 0 ? <Empty text="No goods received yet." /> : (
        <table>
          <thead><tr><th>Received</th><th>By</th><th>Items</th></tr></thead>
          <tbody>{deliveries.map((d) => <tr key={d.id}><td>{shortDate(d.received_date)}</td><td>{d.received_by ?? "—"}</td><td>{d.items.map((i: any) => `${i.quantity_received} × item ${i.po_item_id}`).join(", ")}</td></tr>)}</tbody>
        </table>
      )}
    </Modal>
  );
}

export default function PurchaseOrders() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const { names: suppliers } = useLookup("/suppliers");
  const { data, loading, error, reload } = useList("/purchase-orders", { status, page, limit: 10 });

  return (
    <>
      <PageHeader title="Purchase orders" subtitle="Track orders from draft to goods received." />
      <Card>
        <div className="toolbar">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {["draft", "issued", "partially_received", "received", "cancelled"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty text="No purchase orders found." /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>PO number</th><th>Supplier</th><th>Status</th><th>Order date</th><th>Expected</th><th className="num">Total</th></tr></thead>
              <tbody>
                {data.items.map((p: any) => (
                  <tr key={p.id} className="clickable" onClick={() => setOpenId(p.id)}>
                    <td><strong>{p.po_number}</strong></td><td>{suppliers[p.supplier_id] ?? `#${p.supplier_id}`}</td><td><Badge value={p.status} /></td>
                    <td>{shortDate(p.order_date)}</td><td>{shortDate(p.expected_delivery_date)}</td><td className="num">{money(p.total_amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
      {openId !== null && <Detail id={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
    </>
  );
}
