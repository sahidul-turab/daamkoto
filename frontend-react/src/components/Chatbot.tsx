/**
 * Chatbot — agentic AI assistant panel.
 *
 * Renders rich blocks (product lists, build sheets, compat reports, price history,
 * deal lists) and executes UI action directives (apply filters, add to build, etc.).
 *
 * Conversation is persisted in localStorage so it survives panel close/reopen.
 */
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle, ArrowDownCircle, Bot, CheckCircle2,
  ChevronRight, Send, Sparkles, TrendingDown, TrendingUp,
  Minus, X, Zap, Package
} from "lucide-react";
import { api } from "../api";
import { formatBDT } from "../lib/format";
import type {
  AgentAction, AgentBlock, BuildSheetBlock, ChatContext,
  CompatReportBlock, DealListBlock, PriceHistoryBlock,
  ProductListBlock, ProductSummary
} from "../types";

// ── Suggestion chips ──────────────────────────────────────────────────────

const SUGGESTIONS = [
  "Build me a 90,000 taka gaming PC",
  "Find cheapest RTX 4060 and check if price dropped",
  "16GB DDR5 RAM under 8000 taka",
  "What are today's best deals?",
];

// ── Message type ──────────────────────────────────────────────────────────

interface Msg {
  role: "user" | "assistant";
  content: string;
  blocks?: AgentBlock[];
}

const STORAGE_KEY = "daamkoto:chat:v2";

function loadHistory(): Msg[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Msg[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(msgs: Msg[]) {
  try {
    // Keep only last 40 messages to avoid quota issues
    localStorage.setItem(STORAGE_KEY, JSON.stringify(msgs.slice(-40)));
  } catch { /* ignore */ }
}

// ── Block renderers ───────────────────────────────────────────────────────

function ProductListBlockView({
  block, onOpen,
}: { block: ProductListBlock; onOpen: (p: ProductSummary) => void }) {
  const [showAll, setShowAll] = useState(false);
  const items = showAll ? block.products : block.products.slice(0, 5);
  if (!block.products.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-4">
        {block.title} ({block.total} total)
      </div>
      {items.map((p) => (
        <button
          key={p.id}
          onClick={() => onOpen(p)}
          className="flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2 text-left transition-colors hover:border-brand/40"
        >
          <span className="line-clamp-1 text-xs text-ink">{p.name}</span>
          <div className="flex shrink-0 items-center gap-2">
            {p.cheapest_retailer && (
              <span className="text-[10px] text-ink-4">{p.cheapest_retailer}</span>
            )}
            <span className="text-xs font-bold text-brand">{formatBDT(p.cheapest_price)}</span>
          </div>
        </button>
      ))}
      {!showAll && block.products.length > 5 && (
        <button
          onClick={() => setShowAll(true)}
          className="flex w-full items-center justify-center gap-1 py-1 text-xs text-ink-4 hover:text-ink"
        >
          <ChevronRight className="h-3 w-3" />
          Show all {block.total} results
        </button>
      )}
    </div>
  );
}

function BuildSheetBlockView({
  block, onOpenProduct: _onOpenProduct, onAddToBuild,
}: {
  block: BuildSheetBlock;
  onOpenProduct: (p: ProductSummary) => void;
  onAddToBuild?: (productId: number, slot: string) => void;
}) {
  const compat = block.compatibility;
  const hasErrors = compat?.has_errors;
  return (
    <div className="mt-3 space-y-2">
      {/* Summary */}
      <div className="flex items-center justify-between rounded-lg border border-line bg-surface px-3 py-2">
        <div>
          <div className="text-xs font-bold text-ink capitalize">{block.profile} build</div>
          <div className="text-[11px] text-ink-4">Budget ৳{block.budget_bdt?.toLocaleString()}</div>
        </div>
        <div className="text-right">
          <div className={`text-sm font-bold ${block.within_budget ? "text-green-400" : "text-red-400"}`}>
            ৳{block.total_cost?.toLocaleString()}
          </div>
          <div className="text-[10px] text-ink-4">
            {block.within_budget ? "Within budget ✓" : "Over budget"}
          </div>
        </div>
      </div>

      {/* Slots */}
      {block.slots.map((s) => (
        <div
          key={s.slot}
          className="flex items-center gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2"
        >
          <Package className="h-3.5 w-3.5 shrink-0 text-ink-4" />
          <div className="min-w-0 flex-1">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-4">
              {s.slot}
            </div>
            <div className="line-clamp-1 text-xs text-ink">{s.product_name}</div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-xs font-bold text-brand">{formatBDT(s.cheapest_price)}</div>
            {onAddToBuild && (
              <button
                onClick={() => onAddToBuild(s.product_id, s.slot)}
                className="text-[10px] text-brand/70 hover:text-brand"
              >
                + Add
              </button>
            )}
          </div>
        </div>
      ))}

      {/* Compat summary */}
      {compat && (
        <div className={`rounded-lg border px-3 py-2 text-xs ${hasErrors ? "border-red-500/30 bg-red-950/20 text-red-400" : "border-green-500/30 bg-green-950/20 text-green-400"}`}>
          {hasErrors ? "⚠ Compatibility issues detected" : "✓ All parts compatible"}
        </div>
      )}
    </div>
  );
}

function PriceHistoryBlockView({ block }: { block: PriceHistoryBlock }) {
  const trendIcon = block.trend === "dropping"
    ? <TrendingDown className="h-3.5 w-3.5 text-green-400" />
    : block.trend === "rising"
    ? <TrendingUp className="h-3.5 w-3.5 text-red-400" />
    : <Minus className="h-3.5 w-3.5 text-ink-4" />;

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface px-3 py-2.5 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-ink">
        {trendIcon}
        Price trend: <span className="capitalize">{block.trend}</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[10px] text-ink-4">Current</div>
          <div className="text-xs font-bold text-ink">{formatBDT(block.current_price)}</div>
        </div>
        <div>
          <div className="text-[10px] text-ink-4">All-time low</div>
          <div className="text-xs font-bold text-green-400">{formatBDT(block.all_time_low)}</div>
        </div>
        <div>
          <div className="text-[10px] text-ink-4">All-time high</div>
          <div className="text-xs font-bold text-red-400">{formatBDT(block.all_time_high)}</div>
        </div>
      </div>
      {block.trend === "dropping" && (
        <div className="text-[11px] text-green-400">
          ↓ Price is dropping — good time to buy!
        </div>
      )}
      {block.trend === "rising" && (
        <div className="text-[11px] text-amber-400">
          ↑ Price is rising — consider buying soon.
        </div>
      )}
    </div>
  );
}

function CompatReportBlockView({ block }: { block: CompatReportBlock }) {
  const errors = block.issues.filter((i) => i.level === "error");
  const warns  = block.issues.filter((i) => i.level === "warn");
  const oks    = block.issues.filter((i) => i.level === "ok");
  return (
    <div className="mt-3 space-y-1.5">
      {errors.map((issue, i) => (
        <div key={i} className="flex gap-2 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-xs">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
          <div>
            <div className="font-semibold text-red-400">{issue.title}</div>
            <div className="text-red-400/70">{issue.detail}</div>
          </div>
        </div>
      ))}
      {warns.map((issue, i) => (
        <div key={i} className="flex gap-2 rounded-lg border border-amber-500/30 bg-amber-950/20 px-3 py-2 text-xs">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
          <div>
            <div className="font-semibold text-amber-400">{issue.title}</div>
            <div className="text-amber-400/70">{issue.detail}</div>
          </div>
        </div>
      ))}
      {oks.map((issue, i) => (
        <div key={i} className="flex gap-2 rounded-lg border border-green-500/20 bg-green-950/10 px-3 py-2 text-xs">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-400" />
          <div>
            <div className="font-semibold text-green-400">{issue.title}</div>
            <div className="text-green-400/70">{issue.detail}</div>
          </div>
        </div>
      ))}
      {block.estimated_watts != null && (
        <div className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink-3">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
          Est. {block.estimated_watts}W draw · Recommend {block.recommended_psu}W PSU
        </div>
      )}
    </div>
  );
}

function DealListBlockView({
  block, onOpen,
}: { block: DealListBlock; onOpen: (id: number) => void }) {
  if (!block.deals.length) return null;
  return (
    <div className="mt-3 space-y-1.5">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-ink-4">
        Top deals ({block.count})
      </div>
      {block.deals.slice(0, 8).map((d, i) => (
        <button
          key={i}
          onClick={() => onOpen(d.id)}
          className="flex w-full items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-left hover:border-brand/40"
        >
          <ArrowDownCircle className="h-4 w-4 shrink-0 text-green-400" />
          <div className="min-w-0 flex-1">
            <div className="line-clamp-1 text-xs text-ink">{d.name}</div>
            <div className="text-[10px] text-ink-4">{d.retailer}</div>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-xs font-bold text-brand">{formatBDT(d.current_price)}</div>
            <div className="text-[10px] text-green-400">↓ {d.drop_pct}%</div>
          </div>
        </button>
      ))}
    </div>
  );
}

// ── Unified block dispatcher ──────────────────────────────────────────────

function BlockView({
  block, onOpenProduct, onAddToBuild,
}: {
  block: AgentBlock;
  onOpenProduct: (p: ProductSummary) => void;
  onAddToBuild?: (productId: number, slot: string) => void;
}) {
  // Stub ProductSummary so the drawer fetches real data by ID
  function fakeProduct(id: number, name: string): ProductSummary {
    return {
      id, name, brand: null, match_key: "", model_number: null,
      category: null, specs: {}, cheapest_price: null,
      cheapest_retailer: null, retailer_count: 0, listings: [],
    };
  }

  switch (block.type) {
    case "product_list":
      return <ProductListBlockView block={block} onOpen={onOpenProduct} />;
    case "build_sheet":
      return (
        <BuildSheetBlockView
          block={block}
          onOpenProduct={onOpenProduct}
          onAddToBuild={onAddToBuild}
        />
      );
    case "price_history":
      return <PriceHistoryBlockView block={block} />;
    case "compat_report":
      return <CompatReportBlockView block={block} />;
    case "deal_list":
      return (
        <DealListBlockView
          block={block}
          onOpen={(id) => {
            const deal = (block as DealListBlock).deals.find((d) => d.id === id);
            if (deal) onOpenProduct(fakeProduct(deal.id, deal.name));
          }}
        />
      );
    case "product_detail":
      return (
        <button
          onClick={() => onOpenProduct(block.product)}
          className="mt-2 flex w-full items-center justify-between rounded-lg border border-line bg-surface px-3 py-2 text-left hover:border-brand/40"
        >
          <span className="line-clamp-1 text-xs text-ink">{block.product.name}</span>
          <span className="text-xs font-bold text-brand">{formatBDT(block.product.cheapest_price)}</span>
        </button>
      );
    default:
      return null;
  }
}

// ── Main component ────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
  onOpenProduct: (p: ProductSummary) => void;
  onAddToBuild?: (productId: number, slot: string) => void;
  onApplyFilters?: (category: string, specs: Record<string, string>) => void;
  onOpenDeals?: () => void;
  context?: ChatContext;
}

export function Chatbot({
  open, onClose, onOpenProduct, onAddToBuild, onApplyFilters, onOpenDeals, context,
}: Props) {
  const [messages, setMessages] = useState<Msg[]>(() => loadHistory());
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(""); // "thinking…" / "searching…" etc.
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy, step]);

  // Execute UI action directives from the agent
  function executeActions(actions: AgentAction[]) {
    for (const action of actions) {
      if (action.type === "apply_filters" && onApplyFilters) {
        onApplyFilters(action.category ?? "", action.specs ?? {});
      }
      if (action.type === "open_deals" && onOpenDeals) {
        onOpenDeals();
      }
      if (action.type === "add_to_build" && onAddToBuild) {
        onAddToBuild(action.product_id, action.slot);
      }
      if (action.type === "open_product") {
        // We'll open via the product drawer — fetch stub
        onOpenProduct({
          id: action.product_id, name: `Product #${action.product_id}`,
          brand: null, match_key: "", model_number: null, category: null,
          specs: {}, cheapest_price: null, cheapest_retailer: null,
          retailer_count: 0, listings: [],
        });
      }
    }
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");

    const next: Msg[] = [...messages, { role: "user", content: q }];
    setMessages(next);
    saveHistory(next);
    setBusy(true);

    // Show a "thinking" step indicator for complex queries
    const isComplex = /build|plan|budget|compat|history|compare|deal/i.test(q);
    setStep(isComplex ? "Planning…" : "Searching…");

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await api.chat(q, history, context);

      setStep("");
      const reply: Msg = {
        role: "assistant",
        content: res.text || res.explanation || "Done.",
        blocks: res.blocks,
      };
      const updated = [...next, reply];
      setMessages(updated);
      saveHistory(updated);

      // Execute any UI actions the agent requested
      if (res.actions?.length) {
        executeActions(res.actions);
      }
    } catch (err: unknown) {
      setStep("");
      const errMsg = err instanceof Error ? err.message : "Unknown error";
      const fallback: Msg = {
        role: "assistant",
        content: `I couldn't reach the AI service right now. (${errMsg}) Make sure the backend is running and GROQ_API_KEY or GEMINI_API_KEY is set in .env.`,
      };
      const updated = [...next, fallback];
      setMessages(updated);
      saveHistory(updated);
    } finally {
      setBusy(false);
    }
  }

  function clearHistory() {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:bg-transparent md:backdrop-blur-none"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Panel */}
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
                  <div className="text-sm font-bold">DaamKoto AI</div>
                  <div className="text-[11px] text-ink-4">
                    Builds · Deals · Compatibility · Prices
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {messages.length > 0 && (
                  <button
                    onClick={clearHistory}
                    className="btn-ghost !rounded-lg !px-2 !py-1 text-[11px] text-ink-4"
                    title="Clear conversation"
                  >
                    Clear
                  </button>
                )}
                <button onClick={onClose} className="btn-ghost !rounded-lg !p-2">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
              {messages.length === 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <Bot className="h-4 w-4 text-brand" />
                    What can I help you with?
                  </div>
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
                    {m.blocks?.map((block, bi) => (
                      <BlockView
                        key={bi}
                        block={block}
                        onOpenProduct={onOpenProduct}
                        onAddToBuild={onAddToBuild}
                      />
                    ))}
                  </div>
                </div>
              ))}

              {/* Thinking indicator */}
              {busy && (
                <div className="flex items-center gap-2 text-xs text-ink-4">
                  <div className="flex items-center gap-1">
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/60"
                        style={{ animationDelay: `${i * 0.15}s` }}
                      />
                    ))}
                  </div>
                  <span>{step || "Thinking…"}</span>
                </div>
              )}
            </div>

            {/* Input */}
            <form
              onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex items-center gap-2 border-t border-line p-3"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything about PC parts…"
                className="field"
                disabled={busy}
              />
              <button
                type="submit"
                className="btn-brand !px-3"
                disabled={busy || !input.trim()}
              >
                <Send className="h-4 w-4" />
              </button>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
