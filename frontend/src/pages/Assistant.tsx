import { FormEvent, useEffect, useRef, useState } from "react";
import { api, formatError } from "../api";
import { Badge, Card, PageHeader } from "../ui";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools?: { name: string }[];
  provider?: string;
}

const SUGGESTIONS = [
  "What is our total spend?",
  "Show the monthly spend trend",
  "Which suppliers perform best?",
  "What is the requisition rejection rate?",
  "Spend by department",
];

export default function Assistant() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hi! Ask me about spend, suppliers, requisitions or orders. I answer using live data from the analytics APIs." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" }); }, [messages, busy]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    const history = messages.slice(1).slice(-10).map((m) => ({ role: m.role, content: m.content }));
    setMessages((current) => [...current, { role: "user", content: question }]);
    setInput("");
    setBusy(true);
    try {
      const reply = await api.post("/assistant/chat", { message: question, history });
      setMessages((current) => [...current, { role: "assistant", content: reply.answer, tools: reply.tools_used, provider: reply.provider }]);
    } catch (e) {
      setMessages((current) => [...current, { role: "assistant", content: `Sorry — ${formatError(e)}` }]);
    } finally {
      setBusy(false);
    }
  }

  const submit = (e: FormEvent) => { e.preventDefault(); send(input); };

  return (
    <>
      <PageHeader title="AI analytics assistant" subtitle="Natural-language questions over your procurement data." />
      <Card className="chat">
        <div className="suggestions">{SUGGESTIONS.map((s) => <button key={s} className="btn ghost sm" onClick={() => send(s)} disabled={busy}>{s}</button>)}</div>
        <div className="chat-log" ref={log}>
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.content}
              {m.role === "assistant" && (m.tools?.length || m.provider) ? (
                <div className="chips">
                  {m.tools?.map((t, n) => <span className="chip" key={n}>🔧 {t.name}</span>)}
                  {m.provider && <span className="chip">{m.provider === "llm" ? "AI model" : "rule-based"}</span>}
                </div>
              ) : null}
            </div>
          ))}
          {busy && <div className="bubble assistant muted">Analysing…</div>}
        </div>
        <form className="row" onSubmit={submit}>
          <input className="grow" placeholder="Ask a question about your procurement data…" value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} />
          <button className="btn" disabled={busy || !input.trim()}>Send</button>
        </form>
        <p className="muted" style={{ marginBottom: 0, fontSize: 12 }}>Answers are generated from tool results only. <Badge value="rule-based" /> mode is used when no AI key is configured.</p>
      </Card>
    </>
  );
}
