import { FormEvent, useEffect, useState } from "react";
import { api, formatError } from "../api";
import { MANAGE, useAuth } from "../auth";
import { money, shortDate } from "../format";
import { useList, useLookup } from "../hooks";
import { Badge, Card, Empty, ErrorText, Field, Modal, PageHeader, Pagination, Spinner, useToast } from "../ui";

function NewRfq({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const { items: materials } = useLookup("/materials");
  const { data: approved } = useList("/requisitions", { status: "approved", limit: 100 });
  const [form, setForm] = useState({ title: "", description: "", due_date: "", requisition_id: "" });
  const [lines, setLines] = useState<any[]>([{ material_id: "", quantity: 1 }]);
  const [error, setError] = useState<string | null>(null);
  const fromRequisition = form.requisition_id !== "";

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post("/rfqs", {
        title: form.title,
        description: form.description || null,
        due_date: form.due_date || null,
        requisition_id: fromRequisition ? Number(form.requisition_id) : null,
        items: fromRequisition ? [] : lines.map((l) => ({ material_id: Number(l.material_id), quantity: Number(l.quantity) })),
      });
      toast("RFQ created as draft");
      onSaved();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <Modal title="New request for quotation" onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorText error={error} />
        <Field label="Title"><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required minLength={3} /></Field>
        <div className="form-grid">
          <Field label="Quotations due by"><input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field>
          <Field label="Source requisition" hint="Items are copied from an approved requisition">
            <select value={form.requisition_id} onChange={(e) => setForm({ ...form, requisition_id: e.target.value })}>
              <option value="">None — enter items manually</option>
              {approved?.items.map((r: any) => <option key={r.id} value={r.id}>{r.requisition_number} · {r.department}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Description"><textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        {!fromRequisition && (
          <>
            <div className="section-title">Items</div>
            {lines.map((line, i) => (
              <div key={i} className="item-row" style={{ gridTemplateColumns: "1fr 110px 36px" }}>
                <select value={line.material_id} onChange={(e) => setLines(lines.map((l, n) => (n === i ? { ...l, material_id: e.target.value } : l)))} required>
                  <option value="">Select material…</option>
                  {materials.map((m: any) => <option key={m.id} value={m.id}>{m.name} ({m.sku})</option>)}
                </select>
                <input type="number" min={1} value={line.quantity} onChange={(e) => setLines(lines.map((l, n) => (n === i ? { ...l, quantity: e.target.value } : l)))} required />
                <button type="button" className="icon-btn" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, n) => n !== i))} aria-label="Remove">✕</button>
              </div>
            ))}
            <button type="button" className="btn ghost sm" onClick={() => setLines([...lines, { material_id: "", quantity: 1 }])}>+ Add item</button>
          </>
        )}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn">Create RFQ</button>
        </div>
      </form>
    </Modal>
  );
}

function QuotationForm({ rfq, materials, onDone }: { rfq: any; materials: Record<number, string>; onDone: () => void }) {
  const toast = useToast();
  const { items: suppliers } = useLookup("/suppliers", { status: "active" });
  const [supplierId, setSupplierId] = useState("");
  const [days, setDays] = useState("14");
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/rfqs/${rfq.id}/quotations`, {
        supplier_id: Number(supplierId),
        delivery_days: Number(days),
        items: rfq.items.map((i: any) => ({ rfq_item_id: i.id, unit_price: Number(prices[i.id]) })),
      });
      toast("Quotation recorded");
      onDone();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <form onSubmit={submit} className="card" style={{ background: "#fafbff", marginTop: 12 }}>
      <ErrorText error={error} />
      <div className="form-grid">
        <Field label="Supplier">
          <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)} required>
            <option value="">Select…</option>
            {suppliers.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </Field>
        <Field label="Delivery lead time (days)"><input type="number" min={0} max={365} value={days} onChange={(e) => setDays(e.target.value)} required /></Field>
      </div>
      {rfq.items.map((i: any) => (
        <div key={i.id} className="item-row" style={{ gridTemplateColumns: "1fr 90px 140px" }}>
          <span>{materials[i.material_id] ?? `#${i.material_id}`}</span><span className="muted">× {i.quantity}</span>
          <input type="number" min={0} step="0.01" placeholder="Unit price" value={prices[i.id] ?? ""} onChange={(e) => setPrices({ ...prices, [i.id]: e.target.value })} required />
        </div>
      ))}
      <button className="btn">Save quotation</button>
    </form>
  );
}

function Detail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const [rfq, setRfq] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { names: materials } = useLookup("/materials");

  const load = async () => {
    try {
      const data = await api.get(`/rfqs/${id}`);
      setRfq(data);
      setComparison(await api.get(`/rfqs/${id}/comparison`));
    } catch (e) {
      setError(formatError(e));
    }
  };
  useEffect(() => { load(); }, [id]);

  async function act(message: string, call: () => Promise<any>) {
    try {
      await call();
      toast(message);
      setAdding(false);
      await load();
      onChanged();
    } catch (e) {
      toast(formatError(e), "err");
    }
  }

  if (error) return <Modal title="RFQ" onClose={onClose}><ErrorText error={error} /></Modal>;
  if (!rfq) return <Modal title="RFQ" onClose={onClose}><Spinner /></Modal>;
  const canManage = can(...MANAGE);
  const rows = comparison?.quotations ?? [];

  return (
    <Modal title={`${rfq.rfq_number} · ${rfq.title}`} onClose={onClose} wide>
      <div className="row" style={{ marginBottom: 14 }}><Badge value={rfq.status} /><span className="muted">Due {shortDate(rfq.due_date)}</span></div>
      {rfq.description && <p>{rfq.description}</p>}
      <table>
        <thead><tr><th>Material</th><th className="num">Quantity</th></tr></thead>
        <tbody>{rfq.items.map((i: any) => <tr key={i.id}><td>{materials[i.material_id] ?? `#${i.material_id}`}</td><td className="num">{i.quantity}</td></tr>)}</tbody>
      </table>

      {canManage && (
        <div className="row" style={{ marginTop: 16 }}>
          {rfq.status === "draft" && <button className="btn" onClick={() => act("RFQ published", () => api.post(`/rfqs/${id}/publish`))}>Publish</button>}
          {rfq.status === "published" && <button className="btn ghost" onClick={() => act("RFQ closed", () => api.post(`/rfqs/${id}/close`))}>Close for quotations</button>}
          {["draft", "published", "closed"].includes(rfq.status) && <button className="btn ghost" onClick={() => window.confirm("Cancel this RFQ?") && act("RFQ cancelled", () => api.post(`/rfqs/${id}/cancel`))}>Cancel RFQ</button>}
          {rfq.status === "published" && <button className="btn ghost" onClick={() => setAdding(!adding)}>+ Record quotation</button>}
        </div>
      )}
      {adding && <QuotationForm rfq={rfq} materials={materials} onDone={() => { setAdding(false); load(); onChanged(); }} />}

      <div className="section-title">Quotation comparison</div>
      {rows.length === 0 ? <Empty text="No quotations yet." /> : (
        <>
          <p className="muted" style={{ marginTop: 0 }}>Ranked by price ({comparison.weights.price} pts), delivery speed ({comparison.weights.delivery} pts) and supplier scorecard ({comparison.weights.supplier_score} pts).</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>#</th><th>Supplier</th><th className="num">Total</th><th className="num">Days</th><th className="num">Supplier score</th><th className="num">Composite</th><th>Status</th>{canManage && <th />}</tr></thead>
              <tbody>
                {rows.map((q: any) => (
                  <tr key={q.quotation_id}>
                    <td>{q.rank === 1 ? "★" : q.rank}</td><td><strong>{q.supplier_name}</strong></td><td className="num">{money(q.total_amount)}</td>
                    <td className="num">{q.delivery_days}</td><td className="num">{q.supplier_score ?? "n/a"}</td><td className="num"><strong>{q.composite_score}</strong></td><td><Badge value={q.status} /></td>
                    {canManage && (
                      <td className="right">{["published", "closed"].includes(rfq.status) && <button className="btn success sm" onClick={() => window.confirm(`Award to ${q.supplier_name} and create the purchase order?`) && act("Awarded — purchase order created", () => api.post(`/rfqs/${id}/award`, { quotation_id: q.quotation_id }))}>Award</button>}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {rfq.awarded_po_id && <div className="alert ok" style={{ marginTop: 14 }}>Awarded — purchase order #{rfq.awarded_po_id} created (see Purchase Orders).</div>}
    </Modal>
  );
}

export default function Rfqs() {
  const { can } = useAuth();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const { data, loading, error, reload } = useList("/rfqs", { status, page, limit: 10 });

  return (
    <>
      <PageHeader title="Requests for quotation" subtitle="Collect, compare and award supplier quotations." actions={can(...MANAGE) && <button className="btn" onClick={() => setCreating(true)}>+ New RFQ</button>} />
      <Card>
        <div className="toolbar">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {["draft", "published", "closed", "awarded", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty text="No RFQs yet." /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Number</th><th>Title</th><th>Status</th><th>Due</th><th className="num">Items</th></tr></thead>
              <tbody>
                {data.items.map((r: any) => (
                  <tr key={r.id} className="clickable" onClick={() => setOpenId(r.id)}>
                    <td><strong>{r.rfq_number}</strong></td><td>{r.title}</td><td><Badge value={r.status} /></td><td>{shortDate(r.due_date)}</td><td className="num">{r.items.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
      {creating && <NewRfq onClose={() => setCreating(false)} onSaved={() => { setCreating(false); reload(); }} />}
      {openId !== null && <Detail id={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
    </>
  );
}
