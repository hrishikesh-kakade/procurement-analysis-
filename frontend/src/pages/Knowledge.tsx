import { FormEvent, useRef, useState } from "react";
import { api, formatError } from "../api";
import { MANAGE, useAuth } from "../auth";
import { shortDate } from "../format";
import { useList } from "../hooks";
import { Badge, Card, Empty, ErrorText, Field, Modal, PageHeader, Spinner, useToast } from "../ui";

const SAMPLE_EVAL = JSON.stringify(
  { top_k: 3, with_answers: true, cases: [{ question: "When is an RFQ required?", expected_titles: ["Procurement Policy"], expected_keywords: ["rfq"] }] },
  null, 2,
);

function AskPanel() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setResult(await api.post("/knowledge/ask", { question, top_k: 4 }));
    } catch (err) {
      setError(formatError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Ask the knowledge base" actions={result && <><Badge value={result.grounded ? "approved" : "rejected"} /><span className="muted">{result.grounded ? "grounded in sources" : "no supporting source"}</span></>}>
      <form className="row" onSubmit={ask}>
        <input className="grow" placeholder="e.g. Who must approve a requisition above 100,000?" value={question} onChange={(e) => setQuestion(e.target.value)} minLength={3} required />
        <button className="btn" disabled={busy}>{busy ? "Searching…" : "Ask"}</button>
      </form>
      <ErrorText error={error} />
      {result && (
        <div style={{ marginTop: 16 }}>
          <div className="answer">{result.answer}</div>
          {result.citations.map((c: any) => (
            <div className="citation" key={c.marker}>
              <strong>[{c.marker}] {c.title}</strong> <small>chunk {c.chunk_index + 1} · relevance {c.score}</small>
              <div>{c.snippet}…</div>
            </div>
          ))}
          <p className="muted" style={{ fontSize: 12 }}>Answer mode: {result.provider}</p>
        </div>
      )}
    </Card>
  );
}

function AddDocument({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const selected = file.current?.files?.[0];
      if (selected) {
        const form = new FormData();
        form.append("file", selected);
        if (title) form.append("title", title);
        await api.upload("/knowledge/documents/upload", form);
      } else {
        await api.post("/knowledge/documents", { title, content });
      }
      toast("Document indexed");
      onSaved();
    } catch (err) {
      setError(formatError(err));
    }
  }

  return (
    <Modal title="Add a document" onClose={onClose}>
      <form onSubmit={submit}>
        <ErrorText error={error} />
        <Field label="Title" hint="Defaults to the file name when uploading"><input value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} /></Field>
        <Field label="Upload a .txt or .md file"><input type="file" accept=".txt,.md,text/plain,text/markdown" ref={file} /></Field>
        <Field label="…or paste the text"><textarea rows={8} value={content} onChange={(e) => setContent(e.target.value)} /></Field>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn">Index document</button>
        </div>
      </form>
    </Modal>
  );
}

function Evaluate() {
  const [payload, setPayload] = useState(SAMPLE_EVAL);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setReport(await api.post("/knowledge/evaluate", JSON.parse(payload)));
    } catch (e) {
      setError(e instanceof SyntaxError ? "Invalid JSON" : formatError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Evaluate retrieval quality" actions={<button className="btn ghost sm" onClick={run} disabled={busy}>{busy ? "Running…" : "Run evaluation"}</button>}>
      <p className="muted" style={{ marginTop: 0 }}>Labelled questions → hit-rate@k, MRR, precision@k and (optionally) answer grounding.</p>
      <textarea rows={8} value={payload} onChange={(e) => setPayload(e.target.value)} spellCheck={false} style={{ fontFamily: "ui-monospace, monospace", fontSize: 12.5 }} />
      <ErrorText error={error} />
      {report && (
        <div className="row" style={{ marginTop: 12, gap: 24 }}>
          <span>Hit rate <strong>{report.hit_rate}</strong></span><span>MRR <strong>{report.mrr}</strong></span>
          <span>Precision@k <strong>{report.precision_at_k}</strong></span>{report.grounded_rate !== null && report.grounded_rate !== undefined && <span>Grounded <strong>{report.grounded_rate}</strong></span>}
        </div>
      )}
    </Card>
  );
}

export default function Knowledge() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can(...MANAGE);
  const [adding, setAdding] = useState(false);
  const { data, loading, error, reload } = useList("/knowledge/documents", { limit: 50 });

  async function remove(doc: any) {
    if (!window.confirm(`Remove "${doc.title}" from the knowledge base?`)) return;
    try {
      await api.del(`/knowledge/documents/${doc.id}`);
      toast("Document removed");
      reload();
    } catch (e) {
      toast(formatError(e), "err");
    }
  }

  return (
    <>
      <PageHeader title="Knowledge base" subtitle="Procurement policies, searchable with cited answers." actions={canManage && <button className="btn" onClick={() => setAdding(true)}>+ Add document</button>} />
      <AskPanel />
      <Card title="Indexed documents">
        <ErrorText error={error} />
        {loading && !data ? <Spinner /> : !data?.items.length ? <Empty text="No documents indexed yet. Managers can add policies above." /> : (
          <table>
            <thead><tr><th>Title</th><th>Source</th><th className="num">Chunks</th><th>Added</th>{canManage && <th />}</tr></thead>
            <tbody>
              {data.items.map((d: any) => (
                <tr key={d.id}><td><strong>{d.title}</strong></td><td>{d.source_name ?? "—"}</td><td className="num">{d.chunk_count}</td><td>{shortDate(d.created_at)}</td>
                  {canManage && <td className="right"><button className="btn ghost sm" onClick={() => remove(d)}>Remove</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {canManage && <Evaluate />}
      {adding && <AddDocument onClose={() => setAdding(false)} onSaved={() => { setAdding(false); reload(); }} />}
    </>
  );
}
