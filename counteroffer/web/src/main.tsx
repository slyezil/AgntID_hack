import React, { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Session = {
  buyer_id: string;
  merchant_id: string;
  buyer_display_name: string;
  csrf_token: string;
  expires_at: string;
};

type Message = { turn_id?: string; role: "user" | "assistant"; text: string };
type QuoteLine = {
  sku: string;
  title: string;
  selling_unit: string;
  quantity: number;
  unit_price: { amount: string; currency: string };
};
type Quote = {
  quote_id: string;
  external_name: string;
  version: number;
  status: "DRAFT" | "CHANGED_EXTERNALLY";
  items: QuoteLine[];
  discount_bps: number;
  subtotal: { amount: string; currency: string };
  total_discount: { amount: string; currency: string };
  total_tax: { amount: string; currency: string };
  total: { amount: string; currency: string };
  stock_reserved: false;
  paid: false;
  observed_at: string;
  warnings: string[];
};
type Turn = {
  turn_id: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "NEEDS_CLARIFICATION" | "FAILED" | "INTERRUPTED";
  quotes: Quote[];
};
type ApiError = { error?: { code?: string; message?: string } };
type TurnEvent = {
  turn_id: string;
  sequence: number;
  type: string;
  data: Record<string, unknown>;
};
type PendingSend = { requestId: string; text: string; conversationId: string };

const conversationStorageKey = "counteroffer_conversation_id";
const pendingStorageKey = "counteroffer_pending_send";
const lastTurnStorageKey = "counteroffer_last_turn_id";

class ApiRequestError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiError;
    throw new ApiRequestError(response.status, body.error?.message ?? "The request could not be completed.");
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function money(value: { amount: string; currency: string }): string {
  return `${value.currency} ${value.amount}`;
}

function App() {
  const [phase, setPhase] = useState<"loading" | "signed-out" | "ready">("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [csrf, setCsrf] = useState("");
  const [invite, setInvite] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<PendingSend | null>(null);
  const [turnStatus, setTurnStatus] = useState("");
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);
  const eventSources = useRef(new Map<string, EventSource>());
  const lastSequences = useRef(new Map<string, number>());
  const sendLock = useRef(false);

  const loadConversation = useCallback(async (id: string) => {
    const conversation = await api<{ messages: Message[]; quotes: Quote[] }>(`/api/conversations/${id}`);
    setMessages(conversation.messages);
    setQuotes(conversation.quotes);
    setConversationId(id);
    sessionStorage.setItem(conversationStorageKey, id);
  }, []);

  const openConversation = useCallback(async (csrfToken: string) => {
    const previous = sessionStorage.getItem(conversationStorageKey);
    if (previous) {
      try {
        await loadConversation(previous);
        return;
      } catch {
        sessionStorage.removeItem(conversationStorageKey);
      }
    }
    const created = await api<{ conversation_id: string }>("/api/conversations", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
    });
    await loadConversation(created.conversation_id);
  }, [loadConversation]);

  const acceptSession = useCallback(async (value: Session) => {
    setSession(value);
    setCsrf(value.csrf_token);
    setError("");
    try {
      await openConversation(value.csrf_token);
      setPhase("ready");
      const stored = sessionStorage.getItem(pendingStorageKey);
      if (stored) {
        const restored = JSON.parse(stored) as PendingSend;
        if (restored.conversationId === sessionStorage.getItem(conversationStorageKey)) {
          setPending(restored);
        } else {
          sessionStorage.removeItem(pendingStorageKey);
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not open your quotation conversation.");
      setPhase("signed-out");
    }
  }, [openConversation]);

  useEffect(() => {
    let active = true;
    api<Session>("/api/session")
      .then((value) => {
        if (active) void acceptSession(value);
      })
      .catch(() => {
        if (active) setPhase("signed-out");
      });
    return () => {
      active = false;
      for (const source of eventSources.current.values()) source.close();
      eventSources.current.clear();
    };
  }, [acceptSession]);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, quotes, turnStatus]);

  const signIn = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const value = await api<Session>("/api/session", {
        method: "POST",
        body: JSON.stringify({ code: invite }),
      });
      setInvite("");
      await acceptSession(value);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "This invitation could not be used.");
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    try {
      await api<void>("/api/session", {
        method: "DELETE",
        headers: { "X-CSRF-Token": csrf },
      });
    } catch {
      // Clear this screen even if a stale network connection prevents logout.
    }
    for (const source of eventSources.current.values()) source.close();
    eventSources.current.clear();
    sessionStorage.removeItem(conversationStorageKey);
    sessionStorage.removeItem(pendingStorageKey);
    sessionStorage.removeItem(lastTurnStorageKey);
    setSession(null);
    setMessages([]);
    setQuotes([]);
    setPending(null);
    setPhase("signed-out");
  };

  const attachEvents = (turnId: string) => {
    eventSources.current.get(turnId)?.close();
    const source = new EventSource(`/api/turns/${turnId}/events`);
    eventSources.current.set(turnId, source);
    sessionStorage.setItem(lastTurnStorageKey, turnId);
    setTurnStatus("Waiting for the quotation assistant…");
    let checkingSession = false;

    const handle = (event: Event) => {
      const message = event as MessageEvent<string>;
      let value: TurnEvent;
      try {
        value = JSON.parse(message.data) as TurnEvent;
      } catch {
        return;
      }
      const previous = lastSequences.current.get(turnId) ?? 0;
      if (value.sequence <= previous) return;
      lastSequences.current.set(turnId, value.sequence);

      if (value.type === "turn_started") setTurnStatus("Working on your quotation…");
      if (value.type === "assistant_delta" && typeof value.data.text === "string") {
        const assistantText = value.data.text;
        setMessages((current) => [
          ...current.filter((item) => !(item.role === "assistant" && item.turn_id === turnId)),
          { role: "assistant", turn_id: turnId, text: assistantText },
        ]);
      }
      if (value.type === "tool_denied") {
        setTurnStatus("That request is outside the quotation authority for this task.");
      }
      if (value.type === "turn_completed") {
        void api<Turn>(`/api/turns/${turnId}`)
          .then((turn) => {
            setQuotes((current) => mergeQuotes(current, turn.quotes));
            setTurnStatus(turn.status === "NEEDS_CLARIFICATION" ? "Please review the quotation status." : "Ready for your next request.");
          })
          .catch(() => setTurnStatus("The connection paused. Refresh status to check this turn."));
        source.close();
      }
      if (value.type === "turn_failed") {
        setTurnStatus("This request could not be completed. Your message is saved.");
        source.close();
      }
      if (value.type === "turn_interrupted") {
        setTurnStatus("The local quotation service restarted. Refresh status to check this turn.");
        source.close();
      }
    };

    for (const type of [
      "turn_queued", "turn_started", "assistant_delta", "tool_requested", "tool_finished",
      "tool_denied", "quote_created", "turn_completed", "turn_failed", "turn_interrupted",
    ]) source.addEventListener(type, handle as EventListener);
    source.onerror = () => {
      setTurnStatus("Connection paused. Reconnecting to the saved turn…");
      if (checkingSession) return;
      checkingSession = true;
      void api<Session>("/api/session")
        .then((value) => {
          setSession(value);
          setCsrf(value.csrf_token);
        })
        .catch((reason: unknown) => {
          if (reason instanceof ApiRequestError && reason.status === 401) {
            source.close();
            setSession(null);
            setPhase("signed-out");
          }
        })
        .finally(() => { checkingSession = false; });
    };
  };

  useEffect(() => {
    if (phase !== "ready") return;
    const turnId = sessionStorage.getItem(lastTurnStorageKey);
    if (!turnId) return;
    void api<Turn>(`/api/turns/${turnId}`)
      .then((turn) => {
        setQuotes((current) => mergeQuotes(current, turn.quotes));
        if (turn.status === "QUEUED" || turn.status === "RUNNING") attachEvents(turnId);
        else {
          setTurnStatus(turn.status === "COMPLETED"
            ? "Ready for your next request."
            : `Quotation request: ${turn.status.toLowerCase()}.`);
        }
      })
      .catch(() => sessionStorage.removeItem(lastTurnStorageKey));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase]);

  const sendPending = async (candidate: PendingSend) => {
    if (!session || sendLock.current) return;
    sendLock.current = true;
    setBusy(true);
    setError("");
    setTurnStatus("Saving your request…");
    if (!messages.some((message) => message.turn_id === candidate.requestId && message.role === "user")) {
      setMessages((current) => [...current, { role: "user", turn_id: candidate.requestId, text: candidate.text }]);
    }
    try {
      const accepted = await api<{ turn_id: string; status: string }>(
        `/api/conversations/${candidate.conversationId}/turns`,
        {
          method: "POST",
          headers: { "X-CSRF-Token": csrf },
          body: JSON.stringify({ client_request_id: candidate.requestId, text: candidate.text }),
        },
      );
      setMessages((current) => current.map((message) =>
        message.role === "user" && message.turn_id === candidate.requestId
          ? { ...message, turn_id: accepted.turn_id }
          : message,
      ));
      sessionStorage.removeItem(pendingStorageKey);
      setPending(null);
      attachEvents(accepted.turn_id);
    } catch (reason) {
      setPending(candidate);
      sessionStorage.setItem(pendingStorageKey, JSON.stringify(candidate));
      setError(reason instanceof Error ? reason.message : "Your request is not confirmed yet.");
      setTurnStatus("Your message is saved on this device. Retry will reuse the same request ID.");
    } finally {
      sendLock.current = false;
      setBusy(false);
    }
  };

  const submitMessage = async (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !conversationId || busy) return;
    setDraft("");
    const candidate = { requestId: crypto.randomUUID(), text, conversationId };
    setPending(candidate);
    sessionStorage.setItem(pendingStorageKey, JSON.stringify(candidate));
    await sendPending(candidate);
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const refreshStatus = async () => {
    const turnId = [...eventSources.current.keys()].at(-1);
    if (!turnId) return;
    try {
      const turn = await api<Turn>(`/api/turns/${turnId}`);
      setQuotes((current) => mergeQuotes(current, turn.quotes));
      setTurnStatus(turn.status === "COMPLETED" ? "Ready for your next request." : `Quotation request: ${turn.status.toLowerCase()}.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not refresh turn status.");
    }
  };

  if (phase === "loading") {
    return <main className="loading-shell"><span className="brand-mark">CO</span><p>Opening your quotation workspace…</p></main>;
  }

  if (phase === "signed-out" || !session) {
    return (
      <main className="sign-in-shell">
        <div className="sign-in-card">
          <span className="brand-mark">CO</span>
          <p className="eyebrow">PACKAGING TRADE</p>
          <h1>CounterOffer</h1>
          <p className="lead">Trade quotations, made clear.</p>
          <p className="intro">Sign in with the invitation code shared by your wholesaler. This workspace creates draft quotations only.</p>
          <form onSubmit={signIn} className="sign-in-form">
            <label htmlFor="invite-code">Invitation code</label>
            <input
              id="invite-code"
              autoComplete="one-time-code"
              value={invite}
              onChange={(event) => setInvite(event.target.value)}
              minLength={16}
              maxLength={256}
              required
            />
            {error && <p className="error-message" role="alert">{error}</p>}
            <button className="primary-button" disabled={busy} type="submit">{busy ? "Checking…" : "Open workspace"}</button>
          </form>
          <p className="quiet-note">Synthetic quotation demo · No payments or orders</p>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup"><span className="brand-mark small">CO</span><div><strong>CounterOffer</strong><span>Trade quotations</span></div></div>
        <div className="buyer-lockup"><span className="live-dot" aria-hidden="true" />
          <div><strong>Packaging wholesaler</strong><span>{session.buyer_display_name} · {session.buyer_id}</span></div>
        </div>
        <button className="text-button signout-button" onClick={() => void signOut()}>Sign out</button>
      </header>

      <section className="conversation-layout" aria-label="Quotation conversation">
        <div className="intro-strip">
          <p className="eyebrow">YOUR TRADE DESK</p>
          <h1>What would you like quoted?</h1>
          <p>Ask about packaging products, observed availability, or a draft quotation.</p>
        </div>

        {messages.length === 0 && (
          <div className="suggestion-row" aria-label="Suggested requests">
            {[
              "Quote 200 small cartons and 20 tape rolls",
              "What does one pack of labels contain?",
              "Check availability for 600 small cartons",
            ].map((suggestion) => (
              <button key={suggestion} className="suggestion-chip" onClick={() => setDraft(suggestion)}>{suggestion}</button>
            ))}
          </div>
        )}

        <div className="conversation-feed" ref={feedRef} aria-live="polite" aria-relevant="additions text">
          {messages.map((message, index) => (
            <article className={`message-row ${message.role}`} key={`${message.turn_id ?? "history"}-${message.role}-${index}`}>
              {message.role === "assistant" && <span className="assistant-avatar" aria-hidden="true">CO</span>}
              <div className="message-bubble">
                <span className="message-label">{message.role === "user" ? "You" : "CounterOffer"}</span>
                <p>{message.text}</p>
              </div>
            </article>
          ))}
          {quotes.map((quote) => <QuoteCard key={quote.quote_id} quote={quote} />)}
        </div>

        <div className="status-row" role="status">
          <span>{turnStatus || "Draft quotations only · Stock is not reserved"}</span>
          {turnStatus && <button className="text-button" onClick={() => void refreshStatus()}>Refresh status</button>}
        </div>

        {pending && (
          <div className="retry-panel">
            <p>Your request has not been confirmed by the service.</p>
            <button className="secondary-button" disabled={busy} onClick={() => void sendPending(pending)}>Retry saved request</button>
          </div>
        )}
        {error && <p className="error-message inline-error" role="alert">{error}</p>}

        <form className="composer" onSubmit={submitMessage}>
          <label className="visually-hidden" htmlFor="message">Message CounterOffer</label>
          <textarea
            id="message"
            rows={1}
            maxLength={4000}
            placeholder="Describe the packaging you need…"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onComposerKeyDown}
            disabled={busy || Boolean(pending)}
          />
          <button className="send-button" disabled={busy || Boolean(pending) || !draft.trim()} aria-label="Send message">
            <span aria-hidden="true">↑</span>
          </button>
          <p className="composer-note">Enter to send · Shift + Enter for a new line</p>
        </form>
      </section>
    </main>
  );
}

function QuoteCard({ quote }: { quote: Quote }) {
  return (
    <article className="quote-card" aria-label={`Draft quotation ${quote.quote_id}`}>
      <div className="quote-card-head">
        <div><span className="eyebrow">DRAFT QUOTATION</span><h2>{quote.external_name || quote.quote_id}</h2></div>
        <span className="draft-pill">Draft · v{quote.version}</span>
      </div>
      <div className="quote-lines">
        {quote.items.map((item) => (
          <div className="quote-line" key={item.sku}>
            <div><strong>{item.title}</strong><span>{item.quantity} {item.selling_unit} · {item.sku}</span></div>
            <span>{money(item.unit_price)}</span>
          </div>
        ))}
      </div>
      <div className="quote-totals">
        <div><span>Subtotal</span><strong>{money(quote.subtotal)}</strong></div>
        <div><span>Discount ({(quote.discount_bps / 100).toFixed(2)}%)</span><strong>− {money(quote.total_discount)}</strong></div>
        <div><span>Observed tax</span><strong>{money(quote.total_tax)}</strong></div>
        <div className="total-row"><span>Observed total</span><strong>{money(quote.total)}</strong></div>
      </div>
      {quote.warnings.length > 0 && <p className="quote-warning">{quote.warnings.join(" ")}</p>}
      <p className="quote-footnote">Not paid · Stock not reserved · Observed {new Date(quote.observed_at).toLocaleString()}</p>
    </article>
  );
}

function mergeQuotes(current: Quote[], incoming: Quote[]): Quote[] {
  const byId = new Map(current.map((quote) => [quote.quote_id, quote]));
  for (const quote of incoming) byId.set(quote.quote_id, quote);
  return [...byId.values()];
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
