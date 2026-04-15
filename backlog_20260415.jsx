import { useState, useEffect } from “react”;

const STORAGE_KEY = “rf-backlog-items”;

const DEFAULT_ITEMS = [
{
id: 1,
title: “Quiz Mechanic”,
type: “feature”,
priority: “high”,
description: “Pre-committed answers, EL-mapped difficulty, per-fact performance tracking. Full spec already designed in previous session.”,
status: “ready”
},
{
id: 2,
title: “Visual Facts”,
type: “feature”,
priority: “medium”,
description: “Attach relevant diagrams to facts for visual topics (e.g. Neural Network Architectures, CNN vs transformer comparisons, ResNet skip connections).”,
status: “idea”
},
{
id: 3,
title: “Session Summary”,
type: “feature”,
priority: “medium”,
description: “End-of-session recap: topics covered, EL reached, facts delivered, quiz scores. Useful for spaced repetition planning.”,
status: “idea”
},
{
id: 4,
title: “Spaced Repetition Scheduling”,
type: “feature”,
priority: “medium”,
description: “Track when each fact was seen and suggest revisiting at increasing intervals (1 day → 3 days → 1 week). Classic memory consolidation technique.”,
status: “idea”
},
{
id: 5,
title: “Exam Proximity Mode”,
type: “feature”,
priority: “low”,
description: “As CCA exam approaches, shift toward D-category facts and quiz-heavy sessions rather than new fact delivery.”,
status: “idea”
},
{
id: 6,
title: “Predict My Questions”,
type: “feature”,
priority: “medium”,
description: “After delivering a fact, Claude proactively anticipates follow-up questions the user is likely to ask and surfaces them as tappable options.”,
status: “idea”
},
{
id: 7,
title: “Add the Joke”,
type: “feature”,
priority: “low”,
description: “Occasionally include a topic-relevant joke or humorous aside with a fact. Configurable frequency (e.g. joke mode: on/off).”,
status: “idea”
}
];

const STATUS_META = {
ready:      { label: “Ready”,       color: “#00e5a0” },
idea:       { label: “Idea”,        color: “#7b8cff” },
inprogress: { label: “In Progress”, color: “#ffb347” },
done:       { label: “Done”,        color: “#555566” }
};

const PRIORITY_META = {
high:   { label: “HIGH”, color: “#ff4d6d” },
medium: { label: “MED”,  color: “#ffb347” },
low:    { label: “LOW”,  color: “#7b8cff” }
};

const TYPE_META = {
feature: { label: “FEATURE”, icon: “✦”, color: “#7b8cff” },
bug:     { label: “BUG”,     icon: “⚠”, color: “#ff4d6d” }
};

const FILTERS = [“all”,“feature”,“bug”,“high”,“medium”,“low”,“idea”,“ready”,“inprogress”,“done”];

function Pill({ color, children }) {
return (
<span style={{
fontSize: 9, letterSpacing: 1.2, textTransform: “uppercase”,
background: color + “18”, color, border: `1px solid ${color}44`,
padding: “2px 8px”, borderRadius: 2
}}>
{children}
</span>
);
}

export default function Backlog() {
const [items, setItems]         = useState([]);
const [loading, setLoading]     = useState(true);
const [saving, setSaving]       = useState(false);
const [filter, setFilter]       = useState(“all”);
const [editingId, setEditingId] = useState(null);
const [editBuf, setEditBuf]     = useState({});
const [nextId, setNextId]       = useState(8);

useEffect(() => {
(async () => {
try {
const result = await window.storage.get(STORAGE_KEY);
const parsed = JSON.parse(result.value);
setItems(parsed.items || DEFAULT_ITEMS);
setNextId(parsed.nextId || 8);
} catch {
setItems(DEFAULT_ITEMS);
setNextId(8);
} finally {
setLoading(false);
}
})();
}, []);

const persist = async (newItems, newNextId) => {
setSaving(true);
try {
await window.storage.set(STORAGE_KEY, JSON.stringify({ items: newItems, nextId: newNextId ?? nextId }));
} catch (e) {
console.error(“Storage error:”, e);
} finally {
setSaving(false);
}
};

const startEdit = (item) => {
setEditingId(item.id);
setEditBuf({ …item });
};

const saveEdit = async () => {
const updated = items.map(i => i.id === editingId ? { …editBuf } : i);
setItems(updated);
setEditingId(null);
setEditBuf({});
await persist(updated);
};

const cancelEdit = () => {
if (editBuf._isNew) setItems(items.filter(i => i.id !== editingId));
setEditingId(null);
setEditBuf({});
};

const deleteItem = async (id) => {
const updated = items.filter(i => i.id !== id);
setItems(updated);
await persist(updated);
};

const addItem = () => {
const id = nextId;
const blank = { id, title: “New item”, type: “feature”, priority: “medium”, description: “”, status: “idea”, _isNew: true };
setItems(prev => […prev, blank]);
setNextId(id + 1);
setEditingId(id);
setEditBuf(blank);
};

const displayed = filter === “all”
? items
: items.filter(i => i.type === filter || i.status === filter || i.priority === filter);

const stats = {
total: items.length,
done: items.filter(i => i.status === “done”).length,
high: items.filter(i => i.priority === “high” && i.status !== “done”).length,
};

if (loading) return (
<div style={{ minHeight: “100vh”, background: “#08080f”, display: “flex”, alignItems: “center”, justifyContent: “center”, fontFamily: “‘Courier New’, monospace”, color: “#7b8cff”, letterSpacing: 3, fontSize: 11 }}>
LOADING…
</div>
);

return (
<div style={{ minHeight: “100vh”, background: “#08080f”, fontFamily: “‘Courier New’, monospace”, color: “#e0e0e0” }}>

```
  {/* Header */}
  <div style={{ padding: "32px 32px 0", borderBottom: "1px solid #141420" }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
      <div>
        <div style={{ fontSize: 10, letterSpacing: 4, color: "#7b8cff", marginBottom: 8, textTransform: "uppercase" }}>
          Random Fact · Project Backlog
        </div>
        <div style={{ fontSize: 32, fontWeight: 900, letterSpacing: -1.5, color: "#ffffff", lineHeight: 1 }}>
          BACKLOG
        </div>
        <div style={{ display: "flex", gap: 20, marginTop: 10 }}>
          <span style={{ fontSize: 10, color: "#444", letterSpacing: 1 }}>{stats.total} ITEMS</span>
          <span style={{ fontSize: 10, color: "#00e5a0", letterSpacing: 1 }}>{stats.done} DONE</span>
          {stats.high > 0 && <span style={{ fontSize: 10, color: "#ff4d6d", letterSpacing: 1 }}>{stats.high} HIGH PRIORITY</span>}
          {saving && <span style={{ fontSize: 10, color: "#ffb347", letterSpacing: 1, animation: "pulse 1s infinite" }}>SAVING…</span>}
        </div>
      </div>
      <button onClick={addItem} style={{
        background: "transparent", border: "1px solid #7b8cff", color: "#7b8cff",
        padding: "10px 20px", fontSize: 10, letterSpacing: 2, cursor: "pointer",
        textTransform: "uppercase", fontFamily: "inherit"
      }}
        onMouseEnter={e => { e.target.style.background = "#7b8cff"; e.target.style.color = "#08080f"; }}
        onMouseLeave={e => { e.target.style.background = "transparent"; e.target.style.color = "#7b8cff"; }}
      >
        + NEW
      </button>
    </div>

    {/* Filter strip */}
    <div style={{ display: "flex", gap: 0, overflowX: "auto" }}>
      {FILTERS.map(f => (
        <button key={f} onClick={() => setFilter(f)} style={{
          background: "transparent",
          borderTop: "none", borderLeft: "none", borderRight: "none",
          borderBottom: filter === f ? "2px solid #7b8cff" : "2px solid transparent",
          color: filter === f ? "#7b8cff" : "#444",
          padding: "10px 14px", fontSize: 10, letterSpacing: 1.5,
          cursor: "pointer", textTransform: "uppercase", fontFamily: "inherit",
          whiteSpace: "nowrap"
        }}>
          {f}
        </button>
      ))}
    </div>
  </div>

  {/* List */}
  <div style={{ padding: "8px 0" }}>
    {displayed.length === 0 && (
      <div style={{ padding: "48px 32px", color: "#333", fontSize: 11, letterSpacing: 2, textAlign: "center" }}>
        NO ITEMS
      </div>
    )}

    {displayed.map(item => {
      const isEditing = editingId === item.id;
      const d = isEditing ? editBuf : item;

      return (
        <div key={item.id} style={{
          borderBottom: "1px solid #101018",
          borderLeft: `3px solid ${isEditing ? "#7b8cff" : (PRIORITY_META[d.priority]?.color + "55")}`,
          padding: "16px 28px",
          background: isEditing ? "#0d0d1a" : "transparent"
        }}
          onMouseEnter={e => { if (!isEditing) e.currentTarget.style.background = "#0c0c16"; }}
          onMouseLeave={e => { if (!isEditing) e.currentTarget.style.background = "transparent"; }}
        >
          {isEditing ? (
            <div>
              <input
                value={d.title}
                onChange={e => setEditBuf({ ...editBuf, title: e.target.value })}
                autoFocus
                placeholder="Item title"
                style={{
                  width: "100%", background: "#0a0a14", border: "1px solid #2a2a3e",
                  color: "#fff", fontSize: 14, fontWeight: "bold", padding: "6px 10px",
                  fontFamily: "inherit", marginBottom: 8, letterSpacing: 0.5, boxSizing: "border-box"
                }}
              />
              <textarea
                value={d.description}
                onChange={e => setEditBuf({ ...editBuf, description: e.target.value })}
                placeholder="Description…"
                rows={2}
                style={{
                  width: "100%", background: "#0a0a14", border: "1px solid #2a2a3e",
                  color: "#aaa", fontSize: 11, padding: "6px 10px", resize: "vertical",
                  fontFamily: "inherit", lineHeight: 1.7, marginBottom: 10, boxSizing: "border-box"
                }}
              />
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {[
                  { field: "type",     options: ["feature","bug"] },
                  { field: "priority", options: ["high","medium","low"] },
                  { field: "status",   options: ["idea","ready","inprogress","done"] }
                ].map(({ field, options }) => (
                  <select key={field} value={d[field]}
                    onChange={e => setEditBuf({ ...editBuf, [field]: e.target.value })}
                    style={{
                      background: "#0a0a14", border: "1px solid #2a2a3e", color: "#aaa",
                      fontSize: 10, padding: "4px 8px", fontFamily: "inherit",
                      letterSpacing: 1, textTransform: "uppercase"
                    }}
                  >
                    {options.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                ))}
                <button onClick={saveEdit} style={{
                  background: "#00e5a0", border: "none", color: "#08080f",
                  fontSize: 10, padding: "5px 14px", cursor: "pointer",
                  letterSpacing: 1, fontFamily: "inherit", fontWeight: "bold"
                }}>SAVE</button>
                <button onClick={cancelEdit} style={{
                  background: "transparent", border: "1px solid #333", color: "#555",
                  fontSize: 10, padding: "5px 14px", cursor: "pointer",
                  letterSpacing: 1, fontFamily: "inherit"
                }}>CANCEL</button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 6, marginBottom: 7, flexWrap: "wrap", alignItems: "center" }}>
                  <Pill color={TYPE_META[d.type]?.color}>{TYPE_META[d.type]?.icon} {TYPE_META[d.type]?.label}</Pill>
                  <Pill color={PRIORITY_META[d.priority]?.color}>{PRIORITY_META[d.priority]?.label}</Pill>
                  <Pill color={STATUS_META[d.status]?.color}>{STATUS_META[d.status]?.label}</Pill>
                </div>
                <div style={{
                  fontSize: 14, fontWeight: "bold", letterSpacing: 0.3,
                  color: d.status === "done" ? "#333" : "#e8e8e8",
                  textDecoration: d.status === "done" ? "line-through" : "none",
                  marginBottom: d.description ? 5 : 0
                }}>
                  {d.title}
                </div>
                {d.description && (
                  <div style={{ fontSize: 11, color: "#555", lineHeight: 1.7, maxWidth: 560 }}>
                    {d.description}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button onClick={() => startEdit(item)} style={{
                  background: "transparent", border: "1px solid #1e1e2e", color: "#444",
                  fontSize: 9, padding: "4px 10px", cursor: "pointer",
                  letterSpacing: 1, fontFamily: "inherit"
                }}
                  onMouseEnter={e => { e.target.style.borderColor = "#7b8cff"; e.target.style.color = "#7b8cff"; }}
                  onMouseLeave={e => { e.target.style.borderColor = "#1e1e2e"; e.target.style.color = "#444"; }}
                >EDIT</button>
                <button onClick={() => deleteItem(item.id)} style={{
                  background: "transparent", border: "1px solid #1e1e2e", color: "#333",
                  fontSize: 9, padding: "4px 10px", cursor: "pointer",
                  letterSpacing: 1, fontFamily: "inherit"
                }}
                  onMouseEnter={e => { e.target.style.borderColor = "#ff4d6d"; e.target.style.color = "#ff4d6d"; }}
                  onMouseLeave={e => { e.target.style.borderColor = "#1e1e2e"; e.target.style.color = "#333"; }}
                >DEL</button>
              </div>
            </div>
          )}
        </div>
      );
    })}
  </div>
</div>
```

);
}
