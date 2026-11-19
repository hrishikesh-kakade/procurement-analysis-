import { FormEvent, useState } from "react";
import { api, formatError } from "../api";
import { useAuth } from "../auth";
import { label, shortDate } from "../format";
import { useList } from "../hooks";
import { Badge, Card, Empty, ErrorText, Field, Modal, PageHeader, Pagination, Spinner, useToast } from "../ui";

const ROLES = ["admin", "procurement_manager", "approver", "requester", "viewer"];

function NewUser({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "viewer" });
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post("/users", form);
      toast("User created");
      onSaved();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <Modal title="New user" onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorText error={error} />
        <Field label="Full name"><input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} /></Field>
        <Field label="Email"><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
        <Field label="Temporary password" hint="At least 8 characters with a letter and a digit"><input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={8} autoComplete="new-password" /></Field>
        <Field label="Role"><select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}</select></Field>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn">Create user</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const { data, loading, error, reload } = useList("/users", { page, limit: 15 });

  async function update(id: number, patch: any, message: string) {
    try {
      await api.patch(`/users/${id}`, patch);
      toast(message);
      reload();
    } catch (e) {
      toast(formatError(e), "err");
    }
  }

  return (
    <>
      <PageHeader title="Users & roles" subtitle="Control who can view, request, approve and manage." actions={<button className="btn" onClick={() => setCreating(true)}>+ New user</button>} />
      <Card>
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty /> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th /></tr></thead>
              <tbody>
                {data.items.map((u: any) => (
                  <tr key={u.id}>
                    <td><strong>{u.full_name}</strong>{u.id === me?.id && <span className="muted"> (you)</span>}</td><td>{u.email}</td>
                    <td>
                      <select style={{ width: "auto" }} value={u.role} disabled={u.id === me?.id} onChange={(e) => update(u.id, { role: e.target.value }, "Role updated")}>
                        {ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}
                      </select>
                    </td>
                    <td><Badge value={u.is_active ? "active" : "inactive"} /></td><td>{shortDate(u.last_login_at)}</td>
                    <td className="right">{u.id !== me?.id && <button className="btn ghost sm" onClick={() => update(u.id, { is_active: !u.is_active }, u.is_active ? "User deactivated" : "User activated")}>{u.is_active ? "Deactivate" : "Activate"}</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}
      </Card>
      {creating && <NewUser onClose={() => setCreating(false)} onSaved={() => { setCreating(false); reload(); }} />}
    </>
  );
}
