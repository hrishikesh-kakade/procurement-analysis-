import { FormEvent, useState } from "react";
import { api, formatError } from "../api";
import { MANAGE, useAuth } from "../auth";
import { useDebounced, useList } from "../hooks";
import { Badge, Card, Empty, ErrorText, Field, Modal, PageHeader, Pagination, Spinner, useToast } from "../ui";

const EMPTY = { name: "", category: "", email: "", phone: "", address: "", status: "active" };

function SupplierForm({ supplier, onClose, onSaved }: { supplier: any | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState<any>(supplier ? { ...EMPTY, ...supplier } : EMPTY);
  const [error, setError] = useState<string | null>(null);
  const set = (key: string, value: string) => setForm({ ...form, [key]: value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = { name: form.name, category: form.category, email: form.email, phone: form.phone || null, address: form.address || null, status: form.status };
    try {
      if (supplier) await api.put(`/suppliers/${supplier.id}`, body);
      else await api.post("/suppliers", body);
      toast(supplier ? "Supplier updated" : "Supplier created");
      onSaved();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <Modal title={supplier ? "Edit supplier" : "New supplier"} onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorText error={error} />
        <div className="form-grid">
          <Field label="Name"><input value={form.name} onChange={(e) => set("name", e.target.value)} required minLength={2} /></Field>
          <Field label="Category"><input value={form.category} onChange={(e) => set("category", e.target.value)} required minLength={2} placeholder="e.g. electronics" /></Field>
          <Field label="Email"><input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required /></Field>
          <Field label="Phone"><input value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} /></Field>
          <div className="full"><Field label="Address"><input value={form.address ?? ""} onChange={(e) => set("address", e.target.value)} /></Field></div>
          <Field label="Status">
            <select value={form.status} onChange={(e) => set("status", e.target.value)}>
              <option value="active">Active</option><option value="inactive">Inactive</option><option value="blacklisted">Blacklisted</option>
            </select>
          </Field>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn">Save</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Suppliers() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can(...MANAGE);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<any | null | undefined>(undefined);
  const q = useDebounced(search);
  const cat = useDebounced(category);
  const { data, loading, error, reload } = useList("/suppliers", { search: q, category: cat, status, sort_by: sortBy, order, page, limit: 10 });

  async function remove(supplier: any) {
    if (!window.confirm(`Delete ${supplier.name}?`)) return;
    try {
      await api.del(`/suppliers/${supplier.id}`);
      toast("Supplier deleted");
      reload();
    } catch (err) {
      toast(formatError(err), "err");
    }
  }

  return (
    <>
      <PageHeader title="Suppliers" subtitle="Maintain the approved supplier list." actions={canManage && <button className="btn" onClick={() => setEditing(null)}>+ New supplier</button>} />
      <Card>
        <div className="toolbar">
          <input placeholder="Search by name…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          <input placeholder="Category" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} />
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="blacklisted">Blacklisted</option>
          </select>
          <select value={`${sortBy}:${order}`} onChange={(e) => { const [s, o] = e.target.value.split(":"); setSortBy(s); setOrder(o); }}>
            <option value="created_at:desc">Newest first</option><option value="name:asc">Name A–Z</option><option value="name:desc">Name Z–A</option><option value="category:asc">Category</option>
          </select>
        </div>
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty text="No suppliers match your filters." /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Category</th><th>Email</th><th>Phone</th><th>Status</th>{canManage && <th />}</tr></thead>
              <tbody>
                {data.items.map((s: any) => (
                  <tr key={s.id}>
                    <td><strong>{s.name}</strong></td><td>{s.category}</td><td>{s.email}</td><td>{s.phone ?? "—"}</td><td><Badge value={s.status} /></td>
                    {canManage && (
                      <td className="right"><div className="row" style={{ justifyContent: "flex-end" }}>
                        <button className="btn ghost sm" onClick={() => setEditing(s)}>Edit</button>
                        <button className="btn ghost sm" onClick={() => remove(s)}>Delete</button>
                      </div></td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
      {editing !== undefined && <SupplierForm supplier={editing} onClose={() => setEditing(undefined)} onSaved={() => { setEditing(undefined); reload(); }} />}
    </>
  );
}
