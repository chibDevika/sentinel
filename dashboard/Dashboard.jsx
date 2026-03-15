// Dashboard.jsx — Sentinel
// Reads from /data/dashboard_state.json (served from project root)

const { useState, useEffect, useCallback } = React;

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

function useDashboardData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`/data/dashboard_state.json?t=${Date.now()}`);
      if (!res.ok) throw new Error("Failed to load dashboard state");
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatAmount(amount) {
  if (amount == null) return "—";
  return (
    "₹" +
    Number(amount).toLocaleString("en-IN", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })
  );
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

// ---------------------------------------------------------------------------
// State badge
// ---------------------------------------------------------------------------

const STATE_CONFIG = {
  ORDER_CONFIRMED: {
    label: "Confirmed",
    color: "#71717a",
    bg: "rgba(113,113,122,0.15)",
    pulse: false,
  },
  ORDER_SHIPPED: {
    label: "Shipped",
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.15)",
    pulse: false,
  },
  DELIVERY_EXPECTED: {
    label: "In Transit",
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.15)",
    pulse: false,
  },
  DELIVERY_DELAY_COMMUNICATED: {
    label: "Delayed",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.15)",
    pulse: true,
  },
  DELIVERED: {
    label: "Delivered",
    color: "#22c55e",
    bg: "rgba(34,197,94,0.12)",
    pulse: false,
  },
  RETURN_REQUESTED: {
    label: "Return Requested",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.15)",
    pulse: false,
  },
  RETURN_PICKUP_PENDING: {
    label: "Pickup Pending",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.15)",
    pulse: true,
  },
  RETURN_PICKED_UP: {
    label: "Picked Up",
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.15)",
    pulse: false,
  },
  REFUND_PENDING: {
    label: "Refund Pending",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.15)",
    pulse: true,
  },
  REFUND_CLAIMED: {
    label: "Refund Claimed",
    color: "#60a5fa",
    bg: "rgba(96,165,250,0.15)",
    pulse: false,
  },
  RESOLVED: {
    label: "✓ Resolved",
    color: "#22c55e",
    bg: "rgba(34,197,94,0.12)",
    pulse: false,
  },
  REFUND_REJECTED: {
    label: "✕ Rejected",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.15)",
    pulse: false,
  },
  AMOUNT_MISMATCH: {
    label: "⚠ Mismatch",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.15)",
    pulse: true,
  },
  AMBIGUOUS_VENDOR_RESPONSE: {
    label: "Ambiguous",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.15)",
    pulse: false,
  },
  NON_REFUNDABLE: {
    label: "Non-Refundable",
    color: "#ef4444",
    bg: "rgba(239,68,68,0.15)",
    pulse: false,
  },
};

function StateBadge({ state }) {
  const cfg = STATE_CONFIG[state] || {
    label: state,
    color: "#71717a",
    bg: "rgba(113,113,122,0.15)",
    pulse: false,
  };
  const pulseClass = cfg.pulse
    ? cfg.color === "#ef4444"
      ? "pulse-red"
      : "pulse-amber"
    : "";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${pulseClass}`}
      style={{
        color: cfg.color,
        background: cfg.bg,
        border: `1px solid ${cfg.color}30`,
      }}
    >
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Timeline stepper (horizontal, shown in expanded order row)
// ---------------------------------------------------------------------------

function Timeline({ steps }) {
  if (!steps || steps.length === 0) return null;

  // Only show steps up to and including the first non-pending step after current
  const lastMeaningfulIndex = steps.reduce(
    (acc, s, i) => (s.status !== "pending" ? i : acc),
    -1,
  );
  const visibleSteps = steps.slice(0, Math.max(lastMeaningfulIndex + 2, 3));

  const circleStyle = (status) => {
    if (status === "done")
      return { background: "#22c55e", border: "2px solid #22c55e" };
    if (status === "current")
      return {
        background: "transparent",
        border: "2px solid #f59e0b",
        animation: "pulse-border 2s infinite",
      };
    if (status === "overdue")
      return { background: "#ef4444", border: "2px solid #ef4444" };
    return { background: "transparent", border: "2px solid #27272a" };
  };

  const circleContent = (status) => {
    if (status === "done")
      return <span style={{ color: "#0e0e10", fontSize: "10px" }}>✓</span>;
    if (status === "overdue")
      return <span style={{ color: "white", fontSize: "10px" }}>!</span>;
    if (status === "current")
      return <span style={{ color: "#f59e0b", fontSize: "8px" }}>●</span>;
    return null;
  };

  return (
    <div style={{ padding: "16px 0 8px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 0 }}>
        {visibleSteps.map((step, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              alignItems: "flex-start",
              flex: i < visibleSteps.length - 1 ? 1 : "none",
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                minWidth: 80,
              }}
            >
              <div
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  ...circleStyle(step.status),
                }}
              >
                {circleContent(step.status)}
              </div>
              <span
                style={{
                  fontSize: 11,
                  color: step.status === "pending" ? "#71717a" : "#fafafa",
                  marginTop: 6,
                  textAlign: "center",
                  lineHeight: 1.3,
                }}
              >
                {step.step}
              </span>
              {step.date && (
                <span style={{ fontSize: 10, color: "#71717a", marginTop: 2 }}>
                  {formatDate(step.date)}
                </span>
              )}
              {step.status === "overdue" && (
                <span style={{ fontSize: 10, color: "#ef4444", marginTop: 2 }}>
                  Overdue
                </span>
              )}
            </div>
            {i < visibleSteps.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  marginTop: 11,
                  background: step.status === "done" ? "#22c55e" : "#27272a",
                }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Orders tab
// ---------------------------------------------------------------------------

const CLOSED_STATES = new Set([
  "DELIVERED",
  "RESOLVED",
  "ORDER_CONFIRMED",
  "ORDER_SHIPPED",
  "RETURN_REQUESTED",
  "RETURN_PICKED_UP",
  "REFUND_CLAIMED",
]);

const ATTENTION_STATES = new Set([
  "DELIVERY_DELAY_COMMUNICATED",
  "RETURN_PICKUP_PENDING",
  "REFUND_PENDING",
  "REFUND_REJECTED",
  "AMOUNT_MISMATCH",
  "NON_REFUNDABLE",
  "AMBIGUOUS_VENDOR_RESPONSE",
]);

function nextActionText(order) {
  const state = order.state;
  if (
    state === "DELIVERY_EXPECTED" ||
    state === "DELIVERY_DELAY_COMMUNICATED"
  ) {
    if (order.days_overdue) return `Delivery ${order.days_overdue}d overdue`;
    return order.expected_delivery_date
      ? `Exp. ${formatDate(order.expected_delivery_date)}`
      : "—";
  }
  if (state === "RETURN_PICKUP_PENDING") {
    if (order.days_overdue) return `Pickup ${order.days_overdue}d overdue`;
    return "—";
  }
  if (state === "REFUND_PENDING") {
    if (order.days_overdue) return `Refund ${order.days_overdue}d overdue`;
    return order.expected_refund_date
      ? `Exp. ${formatDate(order.expected_refund_date)}`
      : "—";
  }
  if (state === "RESOLVED") return "Complete";
  if (state === "REFUND_REJECTED") return "Manual review needed";
  if (state === "NON_REFUNDABLE") return "Non-refundable";
  return "—";
}

function OrderRow({ order, index, onViewDraft }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="fade-in"
      style={{
        animationDelay: `${index * 40}ms`,
        borderBottom: "1px solid #27272a",
      }}
    >
      {/* Main row */}
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr 110px 180px 1fr 120px 32px",
          alignItems: "center",
          padding: "12px 16px",
          cursor: "pointer",
          gap: 16,
          transition: "background 0.15s",
          background: expanded ? "#1c1c1f" : "transparent",
        }}
        onMouseEnter={(e) => {
          if (!expanded) e.currentTarget.style.background = "#1a1a1d";
        }}
        onMouseLeave={(e) => {
          if (!expanded) e.currentTarget.style.background = "transparent";
        }}
      >
        <span
          style={{
            fontFamily: "DM Mono",
            fontSize: 13,
            color: "#fafafa",
            fontWeight: 500,
          }}
        >
          {order.merchant}
        </span>
        <span
          style={{
            fontSize: 13,
            color: "#a1a1aa",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {order.product}
        </span>
        <span style={{ fontFamily: "DM Mono", fontSize: 13, color: "#fafafa" }}>
          {formatAmount(order.amount)}
        </span>
        <StateBadge state={order.state} />
        <span
          style={{
            fontSize: 12,
            color: order.days_overdue ? "#ef4444" : "#71717a",
            fontFamily: order.days_overdue ? "DM Mono" : "DM Sans",
            fontWeight: order.days_overdue ? 500 : 400,
          }}
        >
          {nextActionText(order)}
        </span>
        <span style={{ fontFamily: "DM Mono", fontSize: 11, color: "#71717a" }}>
          {order.id}
        </span>
        <span style={{ color: "#71717a", fontSize: 12, textAlign: "center" }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div
          style={{
            background: "#1c1c1f",
            borderTop: "1px solid #27272a",
            padding: "16px 24px 20px",
          }}
        >
          {/* Event log — replaces simple stepper */}
          {order.event_log && order.event_log.length > 0 ? (
            <div style={{ marginBottom: 16 }}>
              <p
                style={{
                  fontSize: 11,
                  color: "#71717a",
                  marginBottom: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Event Log
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                {order.event_log.map((ev, i) => {
                  const isInfo = ev.event_type === "info";
                  const isAlert = ev.event_type === "alert";
                  const isCheck = ev.event_type === "check";
                  const dotColor = isAlert
                    ? "#ef4444"
                    : isCheck
                      ? "#a855f7"
                      : isInfo
                        ? "#60a5fa"
                        : "#f59e0b";
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: 12,
                        padding: "10px 0",
                        borderBottom:
                          i < order.event_log.length - 1
                            ? "1px solid #1f1f22"
                            : "none",
                      }}
                    >
                      {/* Dot */}
                      <div
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          background: dotColor,
                          marginTop: 5,
                          flexShrink: 0,
                        }}
                      />
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            flexWrap: "wrap",
                          }}
                        >
                          <span
                            style={{
                              fontFamily: "DM Mono",
                              fontSize: 11,
                              color: "#71717a",
                            }}
                          >
                            {formatDate(ev.email_date || ev.timestamp)}
                          </span>
                          {isCheck ? (
                            <span
                              style={{
                                fontSize: 12,
                                color: "#a855f7",
                                fontWeight: 600,
                                letterSpacing: "0.03em",
                              }}
                            >
                              OVERDUE CHECK
                            </span>
                          ) : (
                            <span style={{ fontSize: 12, color: "#fafafa" }}>
                              {ev.from_state ? `${ev.from_state} → ` : ""}
                              <strong>{ev.to_state}</strong>
                            </span>
                          )}
                          {!isCheck && ev.classified_type && (
                            <span
                              style={{
                                fontSize: 10,
                                color: "#71717a",
                                fontFamily: "DM Mono",
                                background: "#27272a",
                                padding: "1px 6px",
                                borderRadius: 3,
                              }}
                            >
                              {ev.classified_type.replace(/_/g, " ")}
                            </span>
                          )}
                          {isCheck && (
                            <span
                              style={{
                                fontSize: 10,
                                color: "#a855f7",
                                background: "rgba(168,85,247,0.1)",
                                border: "1px solid rgba(168,85,247,0.2)",
                                padding: "1px 6px",
                                borderRadius: 3,
                                fontFamily: "DM Mono",
                              }}
                            >
                              no vendor email · system scan
                            </span>
                          )}
                          {isInfo && (
                            <span
                              style={{
                                fontSize: 10,
                                color: "#60a5fa",
                                background: "rgba(96,165,250,0.1)",
                                border: "1px solid rgba(96,165,250,0.2)",
                                padding: "1px 6px",
                                borderRadius: 3,
                              }}
                            >
                              Vendor update logged
                            </span>
                          )}
                        </div>
                        {ev.trigger && ev.trigger !== "order created" && (
                          <p
                            style={{
                              fontSize: 12,
                              color: "#71717a",
                              marginTop: 3,
                            }}
                          >
                            ↳ {ev.trigger}
                          </p>
                        )}
                        {ev.alert_fired && (
                          <div
                            style={{
                              marginTop: 6,
                              padding: "6px 10px",
                              background: "rgba(239,68,68,0.08)",
                              border: "1px solid rgba(239,68,68,0.2)",
                              borderRadius: 4,
                            }}
                          >
                            <span style={{ fontSize: 11, color: "#ef4444" }}>
                              🚨 {ev.alert_fired}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <Timeline steps={order.timeline} />
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 24,
              marginTop: 16,
            }}
          >
            <div>
              <p
                style={{
                  fontSize: 11,
                  color: "#71717a",
                  marginBottom: 8,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Order Details
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {[
                  ["Order ID", order.id],
                  ["Order Date", formatDate(order.order_date)],
                  ["Amount", formatAmount(order.amount)],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    style={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <span style={{ fontSize: 12, color: "#71717a" }}>{k}</span>
                    <span
                      style={{
                        fontSize: 12,
                        color: "#fafafa",
                        fontFamily: "DM Mono",
                      }}
                    >
                      {v}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p
                style={{
                  fontSize: 11,
                  color: "#71717a",
                  marginBottom: 8,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Key Dates
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {[
                  [
                    "Expected Delivery",
                    formatDate(order.expected_delivery_date),
                  ],
                  ["Delivered", formatDate(order.delivery_date)],
                  [
                    "Return Window Until",
                    formatDate(order.refund_window_until),
                  ],
                  ["Expected Pickup", formatDate(order.expected_pickup_date)],
                  ["Return Pickup", formatDate(order.return_pickup_date)],
                  ["Expected Refund", formatDate(order.expected_refund_date)],
                  ["Bank Credit", formatDate(order.bank_credit_date)],
                ]
                  .filter(([, v]) => v !== "—")
                  .map(([k, v]) => (
                    <div
                      key={k}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span style={{ fontSize: 12, color: "#71717a" }}>
                        {k}
                      </span>
                      <span
                        style={{
                          fontSize: 12,
                          color: "#fafafa",
                          fontFamily: "DM Mono",
                        }}
                      >
                        {v}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
            <div>
              {order.state !== "DELIVERED" && order.email_was_sent && (
                <div>
                  <p
                    style={{
                      fontSize: 11,
                      color: "#71717a",
                      marginBottom: 8,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Email Action
                  </p>
                  <span
                    style={{
                      fontSize: 13,
                      color: "#22c55e",
                      fontFamily: "DM Sans",
                    }}
                  >
                    ✓ Email already sent
                  </span>
                </div>
              )}
              {order.state !== "DELIVERED" &&
                !order.email_was_sent &&
                order.has_draft_email && (
                  <div>
                    <p
                      style={{
                        fontSize: 11,
                        color: "#71717a",
                        marginBottom: 8,
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Draft Email
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewDraft(order);
                      }}
                      style={{
                        background: "rgba(245,158,11,0.1)",
                        border: "1px solid rgba(245,158,11,0.3)",
                        color: "#f59e0b",
                        padding: "6px 14px",
                        borderRadius: 6,
                        fontSize: 13,
                        cursor: "pointer",
                        fontFamily: "DM Sans",
                      }}
                    >
                      View Draft Email →
                    </button>
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function OrdersTab({ orders, onViewDraft }) {
  const [filter, setFilter] = useState("attention");

  const filtered = orders.filter((o) => {
    if (filter === "all") return true;
    if (filter === "resolved") return o.state === "RESOLVED";
    if (filter === "attention")
      return (
        !CLOSED_STATES.has(o.state) &&
        (ATTENTION_STATES.has(o.state) || o.days_overdue > 0)
      );
    return true;
  });

  const filterPills = [
    {
      key: "attention",
      label: "Needs Attention",
      count: orders.filter(
        (o) => ATTENTION_STATES.has(o.state) || o.days_overdue > 0,
      ).length,
    },
    { key: "all", label: "All Orders", count: orders.length },
    {
      key: "resolved",
      label: "Resolved",
      count: orders.filter((o) => o.state === "RESOLVED").length,
    },
  ];

  return (
    <div>
      {/* Filter pills */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {filterPills.map((pill) => (
          <button
            key={pill.key}
            onClick={() => setFilter(pill.key)}
            style={{
              padding: "6px 14px",
              borderRadius: 20,
              fontSize: 13,
              cursor: "pointer",
              fontFamily: "DM Sans",
              transition: "all 0.15s",
              background: filter === pill.key ? "#f59e0b" : "transparent",
              color: filter === pill.key ? "#0e0e10" : "#71717a",
              border:
                filter === pill.key ? "1px solid #f59e0b" : "1px solid #27272a",
              fontWeight: filter === pill.key ? 600 : 400,
            }}
          >
            {pill.label} <span style={{ opacity: 0.7 }}>{pill.count}</span>
          </button>
        ))}
      </div>

      {/* Table header */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr 110px 180px 1fr 120px 32px",
          padding: "8px 16px",
          gap: 16,
          borderBottom: "1px solid #27272a",
        }}
      >
        {[
          "Merchant",
          "Product",
          "Amount",
          "Status",
          "Next Action",
          "Order ID",
          "",
        ].map((h) => (
          <span
            key={h}
            style={{
              fontSize: 11,
              color: "#71717a",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontWeight: 500,
            }}
          >
            {h}
          </span>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div
          style={{
            padding: "48px 16px",
            textAlign: "center",
            color: "#71717a",
          }}
        >
          {filter === "attention"
            ? "No orders need attention ✓"
            : "No orders yet"}
        </div>
      ) : (
        filtered.map((order, i) => (
          <OrderRow
            key={order.id}
            order={order}
            index={i}
            onViewDraft={onViewDraft}
          />
        ))
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alerts tab
// ---------------------------------------------------------------------------

const ALERT_ICONS = {
  refund_overdue: "⏱",
  pickup_overdue: "⏱",
  delivery_overdue: "🚚",
  refund_no_bank_credit: "🔴",
  non_refundable: "ℹ",
  refund_rejected: "✕",
  amount_mismatch: "⚠",
  delivery_delay: "ℹ",
};

function AlertCard({ alert, index, onViewDraft }) {
  const icon = ALERT_ICONS[alert.type] || "⚠";
  const isHigh = alert.severity === "high";

  return (
    <div
      className="fade-in"
      style={{
        animationDelay: `${index * 50}ms`,
        background: "#18181b",
        border: `1px solid ${isHigh ? "rgba(239,68,68,0.3)" : "rgba(245,158,11,0.2)"}`,
        borderRadius: 8,
        padding: "14px 16px",
        marginBottom: 10,
        display: "flex",
        alignItems: "flex-start",
        gap: 14,
      }}
    >
      <span style={{ fontSize: 20, marginTop: 2, flexShrink: 0 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontSize: 14, color: "#fafafa", marginBottom: 4 }}>
          {alert.summary}
        </p>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span
            style={{ fontSize: 12, color: "#71717a", fontFamily: "DM Mono" }}
          >
            {alert.merchant} · {alert.order_id}
          </span>
          <span style={{ fontSize: 11, color: "#52525b" }}>
            {formatDateTime(alert.timestamp)}
          </span>
        </div>
        {alert.reasoning &&
          (alert.reasoning.expected_by || alert.reasoning.overdue_by) && (
            <div
              style={{
                display: "flex",
                gap: 16,
                marginTop: 8,
                flexWrap: "wrap",
              }}
            >
              {alert.reasoning.expected_by && (
                <span
                  style={{
                    fontFamily: "DM Mono",
                    fontSize: 11,
                    color: "#71717a",
                  }}
                >
                  Expected by:{" "}
                  <span style={{ color: "#a1a1aa" }}>
                    {formatDate(alert.reasoning.expected_by)}
                  </span>
                </span>
              )}
              {alert.reasoning.last_check && (
                <span
                  style={{
                    fontFamily: "DM Mono",
                    fontSize: 11,
                    color: "#71717a",
                  }}
                >
                  Last check:{" "}
                  <span style={{ color: "#a1a1aa" }}>
                    {formatDate(alert.reasoning.last_check)}
                  </span>
                </span>
              )}
              {alert.reasoning.overdue_by != null && (
                <span
                  style={{
                    fontFamily: "DM Mono",
                    fontSize: 11,
                    color: "#ef4444",
                    fontWeight: 500,
                  }}
                >
                  Overdue by: {alert.reasoning.overdue_by}d
                </span>
              )}
            </div>
          )}
      </div>
      {alert.has_draft_email && (
        <button
          onClick={() => onViewDraft(alert)}
          style={{
            flexShrink: 0,
            background: "rgba(245,158,11,0.1)",
            border: "1px solid rgba(245,158,11,0.3)",
            color: "#f59e0b",
            padding: "6px 14px",
            borderRadius: 6,
            fontSize: 12,
            cursor: "pointer",
            fontFamily: "DM Sans",
            whiteSpace: "nowrap",
          }}
        >
          View Draft →
        </button>
      )}
    </div>
  );
}

function AlertsTab({ alerts, onViewDraft }) {
  if (alerts.length === 0) {
    return (
      <div style={{ padding: "64px 0", textAlign: "center" }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
        <p style={{ color: "#71717a", fontSize: 15 }}>No active alerts</p>
      </div>
    );
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: "#71717a", marginBottom: 16 }}>
        {alerts.length} active alert{alerts.length !== 1 ? "s" : ""}
      </p>
      {alerts.map((alert, i) => (
        <AlertCard
          key={alert.id}
          alert={alert}
          index={i}
          onViewDraft={onViewDraft}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Analytics tab
// ---------------------------------------------------------------------------

function AnalyticsTab({ analytics, summary, orders }) {
  const { return_rate_by_merchant = [], flagged_merchants = [] } =
    analytics || {};

  const RETURN_STATES = new Set([
    "RETURN_REQUESTED",
    "RETURN_PICKUP_PENDING",
    "RETURN_PICKED_UP",
    "REFUND_PENDING",
    "REFUND_CLAIMED",
    "REFUND_REJECTED",
    "AMOUNT_MISMATCH",
  ]);
  const returnCount = orders.filter(
    (o) =>
      o.return_requested_date ||
      o.return_pickup_date ||
      RETURN_STATES.has(o.state) ||
      (o.state === "RESOLVED" && o.return_pickup_date),
  ).length;
  const returnRate =
    orders.length > 0 ? Math.round((returnCount / orders.length) * 100) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stat cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
        }}
      >
        {[
          { label: "Total Orders", value: summary.total_orders },
          { label: "Total Returns", value: returnCount },
          { label: "Return Rate", value: `${returnRate}%` },
          {
            label: "Pending Refunds",
            value: formatAmount(summary.pending_refund_value),
          },
        ].map(({ label, value }) => (
          <div
            key={label}
            style={{
              background: "#18181b",
              border: "1px solid #27272a",
              borderRadius: 8,
              padding: "20px 24px",
            }}
          >
            <p
              style={{
                fontSize: 12,
                color: "#71717a",
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              {label}
            </p>
            <p
              style={{
                fontSize: 24,
                fontFamily: "DM Mono",
                color: "#fafafa",
                fontWeight: 500,
              }}
            >
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      {return_rate_by_merchant.length > 0 && (
        <div
          style={{
            background: "#18181b",
            border: "1px solid #27272a",
            borderRadius: 8,
            padding: "20px 24px",
          }}
        >
          <p
            style={{
              fontSize: 11,
              color: "#71717a",
              marginBottom: 16,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Return Rate by Merchant
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {return_rate_by_merchant.map(({ merchant, rate }) => (
              <div
                key={merchant}
                style={{ display: "flex", alignItems: "center", gap: 12 }}
              >
                <span
                  style={{
                    width: 110,
                    fontSize: 12,
                    color: "#a1a1aa",
                    fontFamily: "DM Sans",
                    flexShrink: 0,
                    textAlign: "right",
                  }}
                >
                  {merchant}
                </span>
                <div
                  style={{
                    flex: 1,
                    background: "#27272a",
                    borderRadius: 4,
                    height: 20,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.round(rate * 100)}%`,
                      height: "100%",
                      background: "rgba(245,158,11,0.75)",
                      borderRadius: 4,
                      transition: "width 0.6s ease",
                    }}
                  />
                </div>
                <span
                  style={{
                    width: 36,
                    fontSize: 12,
                    color: "#f59e0b",
                    fontFamily: "DM Mono",
                    flexShrink: 0,
                  }}
                >
                  {Math.round(rate * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Flagged merchants table */}
      {flagged_merchants.length > 0 && (
        <div
          style={{
            background: "#18181b",
            border: "1px solid #27272a",
            borderRadius: 8,
            padding: "20px 24px",
          }}
        >
          <p
            style={{
              fontSize: 11,
              color: "#71717a",
              marginBottom: 16,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Top Flagged Merchants
          </p>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Merchant", "Active Alerts"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      fontSize: 11,
                      color: "#71717a",
                      paddingBottom: 12,
                      fontWeight: 500,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {flagged_merchants.map((m) => (
                <tr key={m.merchant} style={{ borderTop: "1px solid #27272a" }}>
                  <td
                    style={{
                      padding: "10px 0",
                      fontSize: 13,
                      color: "#fafafa",
                    }}
                  >
                    {m.merchant}
                  </td>
                  <td
                    style={{
                      padding: "10px 0",
                      fontFamily: "DM Mono",
                      fontSize: 13,
                      color: "#ef4444",
                    }}
                  >
                    {m.alert_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Draft email modal
// ---------------------------------------------------------------------------

function DraftModal({ draft, onClose, onSend }) {
  if (!draft) return null;

  const [copied, setCopied] = useState(false);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(
      `To: ${draft.to}\nSubject: ${draft.subject}\n\n${draft.body}`,
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSend = async () => {
    setSending(true);
    if (draft.order_id && draft.draft_type) {
      await fetch(
        `/api/mark-sent?order_id=${encodeURIComponent(draft.order_id)}&draft_type=${encodeURIComponent(draft.draft_type)}`,
      ).catch(() => {});
      if (onSend) onSend();
    }
    setSent(true);
    setSending(false);
    setTimeout(() => onClose(), 1200);
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.8)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#18181b",
          border: "1px solid #27272a",
          borderRadius: 12,
          width: "100%",
          maxWidth: 640,
          maxHeight: "80vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Modal header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid #27272a",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <p
              style={{
                fontSize: 11,
                color: "#71717a",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 4,
              }}
            >
              Draft Escalation Email
            </p>
            <p style={{ fontSize: 14, color: "#fafafa" }}>{draft.subject}</p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "#71717a",
              cursor: "pointer",
              fontSize: 20,
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Email meta */}
        <div
          style={{ padding: "16px 24px", borderBottom: "1px solid #27272a" }}
        >
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "#71717a", minWidth: 48 }}>
              To:
            </span>
            <span
              style={{ fontSize: 13, color: "#a1a1aa", fontFamily: "DM Mono" }}
            >
              {draft.to}
            </span>
          </div>
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              marginTop: 8,
            }}
          >
            <span style={{ fontSize: 12, color: "#71717a", minWidth: 48 }}>
              Subject:
            </span>
            <span
              style={{ fontSize: 13, color: "#fafafa", fontFamily: "DM Mono" }}
            >
              {draft.subject}
            </span>
          </div>
        </div>

        {/* Email body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
          <pre
            style={{
              fontFamily: "DM Mono",
              fontSize: 13,
              color: "#a1a1aa",
              whiteSpace: "pre-wrap",
              lineHeight: 1.6,
            }}
          >
            {draft.body}
          </pre>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid #27272a",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <p style={{ fontSize: 11, color: "#52525b" }}>
            Sending via your configured Gmail account · DRY_RUN mode
          </p>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={handleCopy}
              style={{
                background: "transparent",
                border: "1px solid #27272a",
                color: "#a1a1aa",
                padding: "8px 16px",
                borderRadius: 6,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              {copied ? "✓ Copied" : "Copy Email"}
            </button>
            <button
              onClick={handleSend}
              disabled={sending || sent}
              style={{
                background: sent ? "#16a34a" : "#f59e0b",
                border: "none",
                color: sent ? "#fff" : "#0e0e10",
                padding: "8px 16px",
                borderRadius: 6,
                fontSize: 13,
                cursor: sending || sent ? "default" : "pointer",
                fontWeight: 600,
                opacity: sending ? 0.7 : 1,
              }}
            >
              {sent ? "✓ Email Sent" : sending ? "Sending…" : "Approve & Send"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Developer controls
// ---------------------------------------------------------------------------

const SCENARIO_META = {
  refund_overdue: {
    label: "Refund Overdue",
    merchant: "TATA CLiQ",
    tag: "escalation triggered",
  },
  happy_path: { label: "Happy Path", merchant: "Nykaa", tag: "full journey ✓" },
  return_pickup_overdue: {
    label: "Return Pickup Overdue",
    merchant: "Myntra",
    tag: "pickup alert",
  },
  delivery_overdue_no_communication: {
    label: "Delivery Overdue",
    merchant: "Amazon",
    tag: "no vendor update",
  },
  refund_no_bank_credit: {
    label: "Fraudulent Refund Claim",
    merchant: "Flipkart",
    tag: "no bank credit",
  },
  qc_failed_refund_rejected: {
    label: "Refund Rejected (QC Fail)",
    merchant: "AJIO",
    tag: "rejected",
  },
  delivery_delayed: {
    label: "Delivery Delayed",
    merchant: "H&M",
    tag: "vendor communicated",
  },
  non_refundable_item: {
    label: "Non-Refundable Item",
    merchant: "Meesho",
    tag: "policy alert",
  },
  no_refund_policy: {
    label: "No Refund Policy Found",
    merchant: "ShopKart",
    tag: "unknown policy",
  },
};

function DevControls({ onRefetch }) {
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeBtn, setActiveBtn] = useState(null);
  const [selectedScenario, setSelectedScenario] = useState("refund_overdue");
  const [scenarios, setScenarios] = useState([]);

  const fetchScenarios = useCallback(async () => {
    try {
      const res = await fetch(`/api/scenarios?t=${Date.now()}`);
      if (res.ok) {
        const data = await res.json();
        setScenarios(data);
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchScenarios();
    const interval = setInterval(fetchScenarios, 3000);
    return () => clearInterval(interval);
  }, [fetchScenarios]);

  async function callPipeline(label, args) {
    setLoading(true);
    setActiveBtn(label);
    setOutput("");
    try {
      const res = await fetch(`/api/pipeline?args=${encodeURIComponent(args)}`);
      const text = await res.text();
      setOutput(text);
      onRefetch();
      fetchScenarios();
    } catch (e) {
      setOutput(
        `Error: ${e.message}\n\nNote: Start serve.py to enable pipeline controls.`,
      );
    } finally {
      setLoading(false);
      setActiveBtn(null);
    }
  }

  const selectedMeta = SCENARIO_META[selectedScenario] || {};
  const scenarioState = scenarios.find((s) => s.id === selectedScenario);
  const isComplete = scenarioState?.complete ?? false;
  const processed = scenarioState?.processed ?? 0;
  const total = scenarioState?.total ?? "?";

  return (
    <div
      style={{
        margin: "32px 0",
        padding: "20px 24px",
        background: "#111113",
        border: "1px solid #27272a",
        borderRadius: 10,
      }}
    >
      <p
        style={{
          fontSize: 11,
          color: "#52525b",
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          marginBottom: 16,
        }}
      >
        Pipeline Controls
      </p>

      {/* Scenario selector */}
      <div style={{ marginBottom: 16 }}>
        <p style={{ fontSize: 12, color: "#71717a", marginBottom: 8 }}>
          Select scenario
        </p>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <select
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            disabled={loading}
            style={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              color: "#fafafa",
              padding: "8px 12px",
              borderRadius: 6,
              fontSize: 13,
              cursor: "pointer",
              flex: "1 1 260px",
            }}
          >
            {Object.entries(SCENARIO_META).map(([id, meta]) => {
              const state = scenarios.find((s) => s.id === id);
              const done = state?.complete ? " ✓" : "";
              return (
                <option key={id} value={id}>
                  {meta.label} — {meta.merchant}
                  {done}
                </option>
              );
            })}
          </select>

          {/* Progress indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 12px",
              background: "#18181b",
              border: "1px solid #27272a",
              borderRadius: 6,
            }}
          >
            <span style={{ fontSize: 12, color: "#71717a" }}>Progress</span>
            <span
              style={{
                fontSize: 13,
                color: isComplete ? "#22c55e" : "#fafafa",
                fontWeight: 600,
                fontFamily: "monospace",
              }}
            >
              {processed} / {total}
            </span>
            {isComplete && (
              <span style={{ fontSize: 11, color: "#22c55e" }}>complete</span>
            )}
          </div>
        </div>

        {/* Scenario tag */}
        {selectedMeta.tag && (
          <p style={{ fontSize: 11, color: "#52525b", marginTop: 6 }}>
            {selectedMeta.merchant} · {selectedMeta.tag}
          </p>
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => callPipeline("next", `--scenario ${selectedScenario}`)}
          disabled={loading || isComplete}
          style={{
            background: isComplete
              ? "#27272a"
              : activeBtn === "next"
                ? "#d97706"
                : "#f59e0b",
            border: "none",
            color: isComplete ? "#52525b" : "#0e0e10",
            padding: "8px 18px",
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 600,
            cursor: isComplete || loading ? "not-allowed" : "pointer",
          }}
        >
          {activeBtn === "next"
            ? "⟳ Processing…"
            : isComplete
              ? "✓ Scenario Done"
              : "▶ Process Next Email"}
        </button>

        <button
          onClick={() => callPipeline("all", "--all")}
          disabled={loading}
          style={{
            background: activeBtn === "all" ? "#d97706" : "transparent",
            border: "1px solid #3f3f46",
            color: "#a1a1aa",
            padding: "8px 14px",
            borderRadius: 6,
            fontSize: 13,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {activeBtn === "all" ? "⟳ Running…" : "Process All"}
        </button>

        <button
          onClick={() => callPipeline("check", "--check")}
          disabled={loading}
          style={{
            background: "transparent",
            border: "1px solid #3f3f46",
            color: "#a1a1aa",
            padding: "8px 14px",
            borderRadius: 6,
            fontSize: 13,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {activeBtn === "check" ? "⟳ Checking…" : "Check Overdue"}
        </button>

        <button
          onClick={() => callPipeline("reset", "--reset")}
          disabled={loading}
          style={{
            background: "transparent",
            border: "1px solid #3f3f46",
            color: "#71717a",
            padding: "8px 14px",
            borderRadius: 6,
            fontSize: 13,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {activeBtn === "reset" ? "⟳ Resetting…" : "Reset All"}
        </button>
      </div>

      {/* Output */}
      {output && (
        <pre
          style={{
            marginTop: 16,
            padding: 12,
            background: "#0a0a0b",
            border: "1px solid #27272a",
            borderRadius: 6,
            fontSize: 11,
            color: "#a1a1aa",
            fontFamily: "DM Mono, monospace",
            whiteSpace: "pre-wrap",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {output}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Email Log tab
// ---------------------------------------------------------------------------

const EMAIL_TYPE_COLORS = {
  order_confirmed: "#71717a",
  order_shipped: "#60a5fa",
  delivery_confirmed: "#22c55e",
  delivery_delayed: "#f59e0b",
  return_requested_confirmation: "#f59e0b",
  return_pickup_confirmed: "#60a5fa",
  refund_initiated: "#60a5fa",
  refund_rejected: "#ef4444",
  ambiguous_vendor_update: "#f59e0b",
  bank_credit_alert: "#22c55e",
};

function EmailLogTab({ emails }) {
  if (!emails || emails.length === 0) {
    return (
      <div style={{ padding: "64px 0", textAlign: "center", color: "#71717a" }}>
        No emails processed yet. Click "Process Next Email" to begin.
      </div>
    );
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: "#71717a", marginBottom: 16 }}>
        {emails.length} email{emails.length !== 1 ? "s" : ""} processed
      </p>
      {/* Header row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "140px 200px 1fr 140px 180px",
          padding: "8px 16px",
          gap: 16,
          borderBottom: "1px solid #27272a",
        }}
      >
        {["Date", "From", "Subject", "Order ID", "Classified As"].map((h) => (
          <span
            key={h}
            style={{
              fontSize: 11,
              color: "#71717a",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {h}
          </span>
        ))}
      </div>
      {[...emails].reverse().map((email, i) => {
        const typeColor = EMAIL_TYPE_COLORS[email.classified_type] || "#71717a";
        return (
          <div
            key={email.email_id}
            className="fade-in"
            style={{
              animationDelay: `${i * 20}ms`,
              display: "grid",
              gridTemplateColumns: "140px 200px 1fr 140px 180px",
              padding: "10px 16px",
              gap: 16,
              borderBottom: "1px solid #1f1f22",
              alignItems: "center",
            }}
          >
            <span
              style={{ fontFamily: "DM Mono", fontSize: 11, color: "#71717a" }}
            >
              {formatDate(email.date)}
            </span>
            <span
              style={{
                fontSize: 12,
                color: "#a1a1aa",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {email.from_addr}
            </span>
            <span
              style={{
                fontSize: 13,
                color: "#fafafa",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {email.subject}
            </span>
            <span
              style={{ fontFamily: "DM Mono", fontSize: 11, color: "#71717a" }}
            >
              {email.order_id}
            </span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "2px 8px",
                borderRadius: 4,
                fontSize: 11,
                fontFamily: "DM Mono",
                color: typeColor,
                background: `${typeColor}18`,
                border: `1px solid ${typeColor}30`,
              }}
            >
              {email.classified_type?.replace(/_/g, " ")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------

function App() {
  const { data, loading, error, refetch } = useDashboardData();
  const [activeTab, setActiveTab] = useState("orders");
  const [modalDraft, setModalDraft] = useState(null);

  // Extract draft email from order or alert for modal
  const handleViewDraft = (orderOrAlert) => {
    // Could be an order (has has_draft_email) or an alert (has draft_email)
    if (orderOrAlert.draft_email) {
      setModalDraft(orderOrAlert.draft_email);
    } else if (data?.alerts) {
      // Find alert for this order that has a draft
      const alert = data.alerts.find(
        (a) => a.order_id === orderOrAlert.id && a.has_draft_email,
      );
      if (alert?.draft_email) setModalDraft(alert.draft_email);
    }
  };

  if (loading)
    return (
      <div
        style={{
          height: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#71717a",
        }}
      >
        <span style={{ fontFamily: "DM Mono", fontSize: 13 }}>Loading...</span>
      </div>
    );

  if (error)
    return (
      <div
        style={{
          height: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <span style={{ color: "#ef4444", fontSize: 14 }}>
          Failed to load dashboard state
        </span>
        <span style={{ color: "#71717a", fontSize: 12, fontFamily: "DM Mono" }}>
          Make sure serve.py is running from the project root
        </span>
      </div>
    );

  const { summary = {}, orders = [], alerts = [], analytics = {} } = data || {};
  const lastUpdated = data?.lastUpdated;

  const TABS = [
    { key: "orders", label: "Orders" },
    { key: "alerts", label: "Alerts" },
    { key: "analytics", label: "Analytics" },
    { key: "email_log", label: "Email Log" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#0e0e10" }}>
      {/* Header */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
          background: "rgba(14,14,16,0.95)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid #27272a",
          padding: "0 32px",
          display: "flex",
          alignItems: "center",
          height: 56,
          gap: 24,
        }}
      >
        <span
          style={{
            fontFamily: "DM Mono",
            fontSize: 15,
            fontWeight: 500,
            color: "#fafafa",
            marginRight: 8,
          }}
        >
          Sentinel
        </span>

        {/* Summary pills */}
        <div style={{ display: "flex", gap: 8, flex: 1 }}>
          {[
            { label: `${summary.total_orders || 0} Orders`, tab: "orders" },
            {
              label: `${summary.active_alerts || 0} Alerts`,
              tab: "alerts",
              alert: summary.active_alerts > 0,
            },
            { label: `${summary.resolved || 0} Resolved`, tab: "orders" },
          ].map(({ label, tab, alert }) => (
            <button
              key={label}
              onClick={() => setActiveTab(tab)}
              style={{
                background: "transparent",
                border: `1px solid ${alert ? "rgba(239,68,68,0.4)" : "#27272a"}`,
                color: alert ? "#ef4444" : "#71717a",
                padding: "4px 12px",
                borderRadius: 20,
                fontSize: 12,
                cursor: "pointer",
                fontFamily: "DM Mono",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Last updated */}
        {lastUpdated && (
          <span
            style={{ fontSize: 11, color: "#52525b", fontFamily: "DM Mono" }}
          >
            Updated {formatDateTime(lastUpdated)}
          </span>
        )}

        {/* Refresh button */}
        <button
          onClick={refetch}
          style={{
            background: "#f59e0b",
            border: "none",
            color: "#0e0e10",
            padding: "7px 16px",
            borderRadius: 6,
            fontSize: 13,
            cursor: "pointer",
            fontWeight: 600,
            fontFamily: "DM Sans",
          }}
        >
          Refresh
        </button>
      </header>

      {/* Tab nav */}
      <div
        style={{
          padding: "0 32px",
          borderBottom: "1px solid #27272a",
          display: "flex",
          gap: 0,
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              background: "none",
              border: "none",
              padding: "14px 20px",
              cursor: "pointer",
              fontFamily: "DM Sans",
              fontSize: 14,
              color: activeTab === tab.key ? "#fafafa" : "#71717a",
              borderBottom:
                activeTab === tab.key
                  ? "2px solid #f59e0b"
                  : "2px solid transparent",
              fontWeight: activeTab === tab.key ? 500 : 400,
              transition: "all 0.15s",
            }}
          >
            {tab.label}
            {tab.key === "alerts" && summary.active_alerts > 0 && (
              <span
                style={{
                  marginLeft: 8,
                  background: "#ef4444",
                  color: "white",
                  fontSize: 10,
                  padding: "1px 6px",
                  borderRadius: 10,
                  fontFamily: "DM Mono",
                }}
              >
                {summary.active_alerts}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Simulation date banner */}
      {data?.simulationDate && (
        <div
          style={{
            background: "rgba(245,158,11,0.06)",
            borderBottom: "1px solid rgba(245,158,11,0.15)",
            padding: "8px 32px",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <span
            style={{ fontSize: 11, color: "#71717a", fontFamily: "DM Mono" }}
          >
            YOU ARE HERE →
          </span>
          <span
            style={{
              fontSize: 13,
              color: "#f59e0b",
              fontFamily: "DM Mono",
              fontWeight: 500,
            }}
          >
            {formatDateTime(data.simulationDate)}
          </span>
          <span style={{ fontSize: 11, color: "#52525b", marginLeft: 4 }}>
            last email processed
          </span>
        </div>
      )}

      {/* Main content */}
      <main
        style={{ maxWidth: 1280, margin: "0 auto", padding: "24px 32px 64px" }}
      >
        {activeTab === "orders" && (
          <OrdersTab orders={orders} onViewDraft={handleViewDraft} />
        )}
        {activeTab === "alerts" && (
          <AlertsTab alerts={alerts} onViewDraft={handleViewDraft} />
        )}
        {activeTab === "analytics" && (
          <AnalyticsTab
            analytics={analytics}
            summary={summary}
            orders={orders}
          />
        )}
        {activeTab === "email_log" && (
          <EmailLogTab emails={data?.email_log || []} />
        )}

        <DevControls onRefetch={refetch} />
      </main>

      {/* Modal */}
      {modalDraft && (
        <DraftModal
          draft={modalDraft}
          onClose={() => setModalDraft(null)}
          onSend={refetch}
        />
      )}
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
