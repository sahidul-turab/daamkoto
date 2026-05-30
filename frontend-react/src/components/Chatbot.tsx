import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Send, Sparkles, X } from "lucide-react";
import { api } from "../api";
import { formatBDT } from "../lib/format";
import type { ProductSummary } from "../types";

interface Msg {
  role: "user" | "assistant";
  content: string;
  products?: ProductSummary[];
}

const SUGGESTIONS = [
  "16GB DDR5 RAM under 8000 taka",
  "Cheapest RTX 4060 with 8GB VRAM",
  "Gold rated 750W modular PSU",
  "NVMe Gen4 1TB SSD",
];

interface Props {
  open: boolean;
  onClose: () => void;
  onOpenProduct: (p: ProductSummary) => void;
}

export function Chatbot({ open, onClose, onOpenProduct }: Props) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    const next: Msg[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    setBusy(true);
    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await api.chat(q, history);
      setMessages([
        ...next,
        {
          role: "assistant",
          content: res.explanation || `Found ${res.total} matching products.`,
          products: res.products,
        },
      ]);
    } catch {
      setMessages([
        ...next,
        {
          role: "assistant",
          content:
            "I couldn't reach the AI service. Make sure the backend is running and ANTHROPIC_API_KEY is set.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:bg-transparent md:backdrop-blur-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed bottom-0 right-0 z-50 flex h-[85vh] w-full flex-col border-l border-t border-line bg-surface shadow-2xl md:inset-y-0 md:h-full md:max-w-md"
            initial={{ x: "100%", opacity: 0.4 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0.4 }}
            transition={{ type: "spring", stiffness: 360, damping: 38 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-line p-4">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-strong/15 text-brand">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-bold">AI Part Finder</div>
                  <div className="text-[11px] text-ink-4">
                    Ask in plain language — real prices only
                  </div>
                </div>
              </div>
              <button onClick={onClose} className="btn-ghost !rounded-lg !p-2">
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-ink-3">
                    Try one of these — I translate it into a structured search and
                    return live prices from the database.
                  </p>
                  <div className="flex flex-col gap-2">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => send(s)}
                        className="rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-left text-sm text-ink-2 transition-colors hover:border-brand/40 hover:text-ink"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => (
                <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[85%] rounded-2xl rounded-br-md bg-brand-strong px-3.5 py-2.5 text-sm text-white"
                        : "max-w-[92%] rounded-2xl rounded-bl-md border border-line bg-surface-2 px-3.5 py-2.5 text-sm text-ink-2"
                    }
                  >
                    {m.content}
                    {m.products && m.products.length > 0 && (
                      <div className="mt-3 space-y-2">
                        {m.products.slice(0, 5).map((p) => (
                          <button
                            key={p.id}
                            onClick={() => onOpenProduct(p)}
                            className="flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-left transition-colors hover:border-brand/40"
                          >
                            <span className="line-clamp-1 text-xs text-ink">
                              {p.name}
                            </span>
                            <span className="shrink-0 text-xs font-bold text-brand">
                              {formatBDT(p.cheapest_price)}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {busy && (
                <div className="flex items-center gap-1.5 text-ink-4">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="h-2 w-2 animate-bounce rounded-full bg-ink-4"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
              className="flex items-center gap-2 border-t border-line p-3"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask for a part…"
                className="field"
                disabled={busy}
              />
              <button type="submit" className="btn-brand !px-3" disabled={busy || !input.trim()}>
                <Send className="h-4 w-4" />
              </button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
