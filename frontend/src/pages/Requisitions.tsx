import { FormEvent, useEffect, useState } from "react";
import { api, formatError } from "../api";
import { APPROVE, MANAGE, REQUISITION_WRITE, useAuth } from "../auth";
import { money, shortDate } from "../format";
import { useList, useLookup } from "../hooks";
import { Badge, Card, Empty, ErrorText, Field, Modal, PageHeader, Pagination, Spinner, useToast } from "../ui";

function NewRequisition({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const { items: materials } = useLookup("/materials");
  const [form, setForm] = useState({ department: "", requested_by: "", justification: "" });
  const [lines, setLines] = useState<any[]>([{ material_id: "", quantity: 1, price: "" }]);
  const [error, setError] = useState<string | null>(null);

  const setLine = (i: number, patch: any) => setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post("/requisitions", {
        ...form,
        justification: form.justification || null,
        items: lines.map((l) => ({
          material_id: Number(l.material_id),
          quantity: Number(l.quantity),
          estimated_unit_price: l.price === "" ? null : Number(l.price),
        })),
      });
      toast("Requisition created as draft");
      onSaved();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <Modal title="New purchase requisition" onClose={onClose} wide>
      <form onSubmit={submit}>
        <ErrorText error={error} />
        <div className="form-grid">
          <Field label="Department"><input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} required minLength={2} /></Field>
          <Field label="Requested by"><input value={form.requested_by} onChange={(e) => setForm({ ...form, requested_by: e.target.value })} required minLength={2} /></Field>
          <div className="full"><Field label="Justification"><textarea rows={2} value={form.justification} onChange={(e) => setForm({ ...form, justification: e.target.value })} /></Field></div>
        </div>
        <div className="section-title">Items</div>
        {lines.map((line, i) => (
          <div className="item-row" key={i}>
            <select value={line.material_id} onChange={(e) => setLine(i, { material_id: e.target.value })} required>
              <option value="">Select material…</option>
              {materials.map((m: any) => <option key={m.id} value={m.id}>{m.name} ({m.sku}) — {money(m.unit_price)}</option>)}
            </select>
            <input type="number" min={1} value={line.quantity} onChange={(e) => setLine(i, { quantity: e.target.value })} aria-label="Quantity" required />
            <input type="number" min={0} step="0.01" placeholder="Unit price" value={line.price} onChange={(e) => setLine(i, { price: e.target.value })} aria-label="Estimated unit price" />
            <button type="button" className="icon-btn" onClick={() => setLines(lines.filter((_, idx) => idx !== i))} disabled={lines.length === 1} aria-label="Remove item">✕</button>
          </div>
        ))}
        <button type="button" className="btn ghost sm" onClick={() => setLines([...lines, { material_id: "", quantity: 1, price: "" }])}>+ Add item</button>
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn">Create draft</button>
        </div>
      </form>
    </Modal>
  );
}

function Detail({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const [req, setReq] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const { names: materialNames } = useLookup("/materials");
  const { items: suppliers } = useLookup("/suppliers", { status: "active" });
  const [supplierId, setSupplierId] = useState("");

  const load = () => api.get(`/requisitions/${id}`).then(setReq).catch((e) => setError(formatError(e)));
  useEffect(() => { load(); }, [id]);

  async function act(label: string, call: () => Promise<any>) {
    try {
      await call();
      toast(label);
      await load();
      onChanged();
    } catch (err) {
      toast(formatError(err), "err");
    }
  }

  if (error) return <Modal title="Requisition" onClose={onClose}><ErrorText error={error} /></Modal>;
  if (!req) return <Modal title="Requisition" onClose={onClose}><Spinner /></Modal>;

  const canWrite = can(...REQUISITION_WRITE);
  return (
    <Modal title={req.requisition_number} onClose={onClose} wide>
      <div className="row" style={{ marginBottom: 14 }}><Badge value={req.status} /><span className="muted">Created {shortDate(req.created_at)}</span></div>
      <dl className="kv">
        <dt>Department</dt><dd>{req.department}</dd>
        <dt>Requested by</dt><dd>{req.requested_by}</dd>
        <dt>Justification</dt><dd>{req.justification ?? "—"}</dd>
        {req.rejection_reason && (<><dt>Rejection reason</dt><dd>{req.rejection_reason}</dd></>)}
        <dt>Estimated total</dt><dd><strong>{money(req.total_estimated_amount)}</strong></dd>
      </dl>
      <table>
        <thead><tr><th>Material</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Line total</th></tr></thead>
        <tbody>
          {req.items.map((i: any) => (
            <tr key={i.id}><td>{materialNames[i.material_id] ?? `#${i.material_id}`}</td><td className="num">{i.quantity}</td><td className="num">{money(i.estimated_unit_price)}</td><td className="num">{money(i.line_total)}</td></tr>
          ))}
        </tbody>
      </table>

      <div className="row" style={{ marginTop: 18 }}>
        {req.status === "draft" && canWrite && (
          <>
            <button className="btn" onClick={() => act("Submitted for approval", () => api.post(`/requisitions/${id}/submit`))}>Submit for approval</button>
            <button className="btn ghost" onClick={() => window.confirm("Delete this draft?") && act("Draft deleted", async () => { await api.del(`/requisitions/${id}`); onClose(); })}>Delete draft</button>
          </>
        )}
        {req.status === "submitted" && can(...APPROVE) && (
          <>
            <button className="btn success" onClick={() => act("Requisition approved", () => api.post(`/requisitions/${id}/approve`))}>Approve</button>
            <button className="btn danger" onClick={() => { const reason = window.prompt("Reason for rejection?"); if (reason) act("Requisition rejected", () => api.post(`/requisitions/${id}/reject`, { reason })); }}>Reject</button>
          </>
        )}
      </div>

      {req.status === "approved" && can(...MANAGE) && (
        <>
          <div className="section-title">Next step</div>
          <div className="row">
            <select style={{ maxWidth: 280 }} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              <option value="">Choose supplier…</option>
              {suppliers.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button className="btn" disabled={!supplierId} onClick={() => act("Purchase order created", () => api.post("/purchase-orders", { supplier_id: Number(supplierId), requisition_id: id }))}>Create purchase order</button>
            <span className="muted">or</span>
            <button className="btn ghost" onClick={() => act("RFQ created", () => api.post("/rfqs", { title: `RFQ for ${req.requisition_number}`, requisition_id: id }))}>Source via RFQ</button>
          </div>
        </>
      )}
    </Modal>
  );
}

export default function Requisitions() {
  const { can } = useAuth();
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const { data, loading, error, reload } = useList("/requisitions", { status, department, page, limit: 10 });

  return (
    <>
      <PageHeader title="Purchase requisitions" subtitle="Request, approve and convert purchases." actions={can(...REQUISITION_WRITE) && <button className="btn" onClick={() => setCreating(true)}>+ New requisition</button>} />
      <Card>
        <div className="toolbar">
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {["draft", "submitted", "approved", "rejected", "converted"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input placeholder="Department" value={department} onChange={(e) => { setDepartment(e.target.value); setPage(1); }} />
        </div>
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty text="No requisitions found." /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Number</th><th>Department</th><th>Requested by</th><th>Status</th><th className="num">Est. total</th><th>Created</th></tr></thead>
              <tbody>
                {data.items.map((r: any) => (
                  <tr key={r.id} className="clickable" onClick={() => setOpenId(r.id)}>
                    <td><strong>{r.requisition_number}</strong></td><td>{r.department}</td><td>{r.requested_by}</td><td><Badge value={r.status} /></td>
                    <td className="num">{money(r.total_estimated_amount)}</td><td>{shortDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
      {creating && <NewRequisition onClose={() => setCreating(false)} onSaved={() => { setCreating(false); reload(); }} />}
      {openId !== null && <Detail id={openId} onClose={() => setOpenId(null)} onChanged={reload} />}
    </>
  );
}
