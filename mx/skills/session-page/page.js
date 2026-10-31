// The session page's keys, the same as diffview's where diffview has one; `?` on the page lists them.
// The window never scrolls: the turns scroll in their own pane, and so do the timeline and the
// band of what waits on the reader, so every scroll here targets one of them.
const root = document.documentElement
const reduce = matchMedia("(prefers-reduced-motion: reduce)")
const behavior = () => (reduce.matches ? "auto" : "smooth")

const scheme = document.getElementById("scheme")
const setTheme = (night) => {
  root.dataset.theme = night ? "night" : "day"
  scheme.setAttribute("aria-label", night ? "switch to day" : "switch to night")
}
scheme.addEventListener("click", () => setTheme(root.dataset.theme !== "night"))
setTheme(root.dataset.theme === "night")

const help = document.getElementById("help")
const toggleHelp = (on = help.hidden) => { help.hidden = !on }
document.getElementById("keys").addEventListener("click", () => toggleHelp())
help.addEventListener("click", (e) => { if (e.target === help) toggleHelp(false) })

const toast = document.getElementById("toast")
let toastTimer = null
// `stay` keeps the toast up until the next one, for a key that waits on more keys
const say = (text, stay = false) => {
  toast.textContent = text
  toast.classList.toggle("on", !!text)
  clearTimeout(toastTimer)
  if (!stay) toastTimer = setTimeout(() => toast.classList.remove("on"), 2200)
}

// diffview's gg: a first g arms, a second within half a second goes to the top
let gArmed = false, gTimer = null
const gg = (go) => {
  if (gArmed) { clearTimeout(gTimer); gArmed = false; go() }
  else { gArmed = true; gTimer = setTimeout(() => (gArmed = false), 500) }
}
const typing = (e) => e.target.matches && e.target.matches("input, textarea, select, [contenteditable]")
const nativeKey = (e) => (e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest("button, a, summary")

const pane = document.getElementById("turns-pane")
const column = document.getElementById("artefacts")
const waiting = document.getElementById("open-questions")
const blocks = [...pane.querySelectorAll("[data-block]")]
// a chat turn is a turn with nothing to open or close, so only a record's turn opens
const turns = blocks.filter((b) => b.matches("details.turn"))
const newest = [...document.querySelectorAll("[data-newest]")]

// ---- the pane's scroll: where a block sits in it, and which block the reader is on

const MARGIN = 6  // the px kept above a block scrolled to the top of the pane
const offsetIn = (el) => el.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop
// The pane follows the cursor after a key and the reader after a scroll of theirs: a wheel, a
// touch or a scrolling key. Only then does the turn at the top become the turn they are on.
let follow = "cursor"
const scrollTo = (top, how = behavior()) => { follow = "cursor"; pane.scrollTo({ top, behavior: how }) }
const atTop = () => {
  const top = pane.getBoundingClientRect().top + MARGIN
  return blocks.find((b) => b.getBoundingClientRect().bottom > top + 1)
}
const inView = () => {
  const p = pane.getBoundingClientRect()
  return blocks.find((b) => { const r = b.getBoundingClientRect(); return r.bottom > p.top + MARGIN && r.top < p.bottom - MARGIN })
}
// a scroll inside `box` that brings `el` into its view, a third of the way down, where it is out of it;
// higher where that would cut off its bottom
const keepInView = (box, el, head = 0) => {
  const b = box.getBoundingClientRect(), r = el.getBoundingClientRect(), room = box.clientHeight - head
  if (r.top < b.top + head || r.bottom > b.bottom) box.scrollTop += r.top - b.top - head - Math.max(0, Math.min(room / 3, room - r.height))
}

let cur = -1
// the cursor's turn is marked in the timeline too, and kept in the timeline's view
const group = (b) => (!b ? null : b.matches("details.turn") ? document.getElementById("a" + b.id.slice(1)) : document.getElementById("a-" + b.id))
const columnHead = column.querySelector(".column-head")
const mark = () => {
  blocks.forEach((b, n) => b.classList.toggle("cur", n === cur))
  const g = group(blocks[cur])
  column.querySelectorAll(".group").forEach((el) => el.classList.toggle("cur", el === g))
  if (g) keepInView(column, g, columnHead.offsetHeight)
}
const focusBlock = (i, how) => {
  if (!blocks.length) return
  cur = Math.max(0, Math.min(blocks.length - 1, i))
  mark()
  const b = blocks[cur]
  ;(b.matches("details") ? b.querySelector(":scope > summary") : b).focus({ preventScroll: true })
  scrollTo(offsetIn(b) - MARGIN, how)
}
document.addEventListener("focusin", (e) => {
  const b = e.target.closest && e.target.closest("[data-block]")
  if (b) { cur = blocks.indexOf(b); mark() }
})

// ---- the control to the newest turn, a chat turn too: marked while it is one the reader has not reached

// the id of the newest block that has been in view in this tab; null until one has
let seen = null
const rank = (id) => { const i = blocks.findIndex((b) => b.id === id); return i < 0 ? Infinity : i }
const reach = () => {
  const b = inView()
  if (b && (seen === null || blocks.indexOf(b) < rank(seen))) seen = b.id
  const fresh = seen !== null && rank(seen) > 0
  newest.forEach((n) => n.classList.toggle("fresh", fresh))
}
const toNewest = () => {
  sheet(false)
  if (!blocks.length) return
  if (blocks[0].matches("details")) blocks[0].open = true
  focusBlock(0)
}
newest.forEach((n) => n.addEventListener("click", toNewest))

// ---- no scrollbars: a fade at whichever edge of a pane has more to scroll to

const faded = []
const fade = (box, head) => {
  const update = () => {
    if (head) box.style.setProperty("--head", head.offsetHeight + "px")
    box.classList.toggle("fade-t", box.scrollTop > 1)
    box.classList.toggle("fade-b", box.scrollTop + box.clientHeight < box.scrollHeight - 1)
  }
  box.addEventListener("scroll", update, { passive: true })
  const sizes = new ResizeObserver(update)
  sizes.observe(box)
  ;[...box.children].forEach((c) => sizes.observe(c))
  // a child added later, the hub's group of pages no turn links, grows the box as much as one there from the start
  new MutationObserver((changes) => {
    changes.forEach((c) => c.addedNodes.forEach((n) => n.nodeType === 1 && sizes.observe(n)))
    update()
  }).observe(box, { childList: true })
  faded.push(update)
}
const refade = () => requestAnimationFrame(() => faded.forEach((u) => u()))
fade(pane)
fade(column, columnHead)
if (waiting) fade(waiting, waiting.querySelector(".divider"))

let ticking = false
pane.addEventListener("scroll", () => {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    ticking = false
    reach()
    if (follow === "scroll") { cur = blocks.indexOf(atTop()); mark() }
  })
}, { passive: true })
const SCROLLING_KEYS = new Set(["PageUp", "PageDown", "Home", "End", "ArrowUp", "ArrowDown", " "])
for (const ev of ["wheel", "touchstart"]) pane.addEventListener(ev, () => (follow = "scroll"), { passive: true })

// ---- what waits on the reader: one card at a time, each answer staged, the batch sent as one message
// Each item is a card the renderer wrote; one shows at a time, and the band takes the keys while the
// focus is in it ([ and ] put it there). What is staged is kept, as the reader stages it, by the hub
// tab the page sits in (`hubWaiting` there keeps a file per session and sends through the session's
// box), or in this browser's storage where no hub frames the page, which then copies the batch
// instead of sending it. Nothing reaches the session but by a send.

const foldBand = document.getElementById("fold-band")
const band = (on = waiting.classList.contains("collapsed")) => {
  waiting.classList.toggle("collapsed", !on)
  foldBand.setAttribute("aria-expanded", on)
  foldBand.firstChild.textContent = on ? "fold " : "show "
  refade()
}
if (foldBand) foldBand.addEventListener("click", () => band())

const cards = waiting ? [...waiting.querySelectorAll(".card")] : []
const ticks = document.getElementById("ticks"), review = document.getElementById("review"), tally = document.getElementById("tally")
const hub = (() => { try { return parent !== window && parent.hubWaiting && parent.hubWaiting.holds(window) ? parent.hubWaiting : null } catch { return null } })()
const STAGED = "session-page:staged:" + document.getElementById("session-id").dataset.copy
// staged: each item's answer by its handle, {pick, act, note}; seen: the artefacts opened or ticked,
// the page's own mark; sent: when each item went in a batch, which keeps it off the cards until a
// turn that ended after the send is on the page
let state = { staged: {}, seen: [], sent: {} }
let loaded = !waiting, at = 0, reviewing = false, noting = null, before = ""
const handles = new Set(cards.map((c) => c.dataset.handle))
const KIND_WORDS = { decide: "decide", do: "do", look: "look at" }

const items = () => cards.filter((c) => !state.sent[c.dataset.handle])
const st = (h) => state.staged[h] || {}
const seenOf = (h) => state.seen.includes(h)
const answer = (s) => [s.pick || s.act, s.note].filter(Boolean).join(", ")
const line = (c) => `${c.dataset.handle}: ${answer(st(c.dataset.handle))}`
const batch = () => items().filter((c) => state.staged[c.dataset.handle]).map(line).join("\n")
const words = () => (hub && hub.words ? hub.words(window) : "").trim()

let saving = Promise.resolve()
const persist = () => {
  const doc = JSON.parse(JSON.stringify(state))
  if (!hub) { try { localStorage.setItem(STAGED, JSON.stringify(doc)) } catch {} return }
  saving = saving.then(() => hub.save(window, doc)).then((r) => { if (r && !r.ok) say(`not kept: ${r.error}`) }, () => say("not kept: the hub tab did not answer"))
}
const stage = (h, patch) => {
  const s = { ...st(h), ...patch }
  Object.keys(s).forEach((k) => { if (!s[k]) delete s[k] })
  if (Object.keys(s).length) state.staged[h] = s
  else delete state.staged[h]
  persist()
  draw()
}
const toggle = (h, key, value) => stage(h, { [key]: st(h)[key] === value ? null : value })
const see = (h, on = !seenOf(h)) => {
  state.seen = state.seen.filter((x) => x !== h).concat(on ? [h] : [])
  persist()
  draw()
}

// What was staged before this render, less what no longer waits; a sent item comes back once a turn
// ended after its send, since that turn says whether it settled.
const ended = [...document.querySelectorAll("[data-block][data-at]")].map((b) => Date.parse(b.dataset.at))
const adopt = (doc) => {
  if (!doc || typeof doc !== "object") return
  const keep = (o) => Object.fromEntries(Object.entries(o || {}).filter(([h]) => handles.has(h)))
  state = { staged: keep(doc.staged), seen: (doc.seen || []).filter((h) => handles.has(h)),
            sent: Object.fromEntries(Object.entries(keep(doc.sent)).filter(([, t]) => !ended.some((e) => e > t))) }
}
if (waiting) {
  const read = hub ? Promise.resolve().then(() => hub.load(window)) : Promise.resolve(JSON.parse(localStorage.getItem(STAGED) || "null"))
  read.then(adopt, () => say("what you staged could not be read")).finally(() => { loaded = true; draw() })
}

// the hub tab's side: the batch its send puts above the box's own words, and the lines it sent, which leave the cards
window.waitingBatch = () => (loaded ? batch() : "")
window.waitingSent = (text) => {
  const sent = new Set(text.split("\n")), now = Date.now(), keys = inBand()
  for (const c of items()) if (state.staged[c.dataset.handle] && sent.has(line(c))) {
    state.sent[c.dataset.handle] = now
    delete state.staged[c.dataset.handle]
  }
  persist()
  // back to the first item still waiting, the keys kept in the band where the review had them
  if (keys) showCard(0)
  else { reviewing = false; at = 0; draw(); waiting.scrollTop = 0 }
}
// a reload under a note being typed would take the field from under the reader's fingers
window.reloadWouldLose = () => noting !== null

const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;")
const staged = (c) => {
  const h = c.dataset.handle, s = st(h)
  const option = s.pick && c.querySelector(`tr[data-option="${s.pick}"] td:nth-child(2)`)
  const picked = option ? `${s.pick} · ${option.firstChild.textContent.trim()}` : s.pick
  const what = picked || s.act
  return what || s.note ? `staged → ${[what, s.note && `note: ${s.note}`].filter(Boolean).join(" · ")}` : ""
}
const drawCard = (c) => {
  const h = c.dataset.handle, s = st(h)
  c.querySelectorAll("tr[data-option]").forEach((tr) => tr.classList.toggle("chosen", tr.dataset.option === s.pick))
  c.classList.toggle("seen", seenOf(h))
  const out = c.querySelector(".staged")
  if (noting === h) return
  out.hidden = !staged(c)
  out.textContent = staged(c)
}
const draw = () => {
  if (!waiting) return
  const list = items()
  at = Math.max(0, Math.min(list.length - 1, at))
  cards.forEach((c) => { c.hidden = reviewing || c !== list[at]; drawCard(c) })
  ticks.replaceChildren()
  let kind = null
  list.forEach((c, n) => {
    if (kind && kind !== c.dataset.kind) ticks.append(Object.assign(document.createElement("span"), { className: "gap" }))
    kind = c.dataset.kind
    const tick = Object.assign(document.createElement("button"), { type: "button", className: "tk", title: `${c.dataset.kind === "look" ? c.querySelector(".rail").textContent : c.dataset.handle} · ${c.querySelector("h3").textContent}` })
    tick.classList.toggle("st", !!state.staged[c.dataset.handle])
    tick.classList.toggle("seen", seenOf(c.dataset.handle))
    tick.classList.toggle("cur", n === at && !reviewing)
    tick.addEventListener("click", () => showCard(n))
    ticks.append(tick)
  })
  const nStaged = list.filter((c) => state.staged[c.dataset.handle]).length, nSent = cards.length - list.length
  const where = Object.assign(document.createElement("span"), { className: "v-meta where" })
  where.textContent = !list.length ? "every item sent" : reviewing ? "review" : `${at + 1} of ${list.length} · ${KIND_WORDS[list[at].dataset.kind]}`
  ticks.append(where)
  tally.textContent = (nStaged ? ` · ${nStaged} staged` : "") + (nSent ? ` · ${nSent} sent` : "")
  review.hidden = !reviewing
  if (reviewing) drawReview(list)
  refade()
}
const drawReview = (list) => {
  const message = [batch(), words()].filter(Boolean).join("\n\n")
  const left = list.filter((c) => !state.staged[c.dataset.handle]).map((c) => (c.dataset.kind === "look" ? c.querySelector(".rail").textContent : c.dataset.handle))
  review.innerHTML = `<h3 class="v-h2">The batch, as the session gets it</h3>` +
    (message ? `<pre>${esc(message)}</pre>` : `<p class="v-small empty">Nothing staged yet.</p>`) +
    `<p class="left-out v-small">${left.length ? `Not answered, so they stay: ${left.join(", ")}.` : "Every item has an answer."}</p>` +
    `<p class="keys-row v-meta"><button type="button" class="key" data-key="Enter"><kbd>↵</kbd> ${hub ? "send" : "copy it: no hub frames this page to send it"}</button>` +
    `<button type="button" class="key" data-key="Escape"><kbd>Esc</kbd> back to the items</button></p>`
}

const inBand = () => !!waiting && waiting.contains(document.activeElement)
const showCard = (n) => {
  if (!waiting) return
  reviewing = false
  at = n
  band(true)
  draw()
  const c = items()[at]
  if (c) { c.focus({ preventScroll: true }); waiting.scrollTop = 0 }
}
const leaveBand = () => { document.activeElement.blur(); if (blocks[cur]) focusBlock(cur) }

const note = (c) => {
  const h = c.dataset.handle, out = c.querySelector(".staged")
  noting = h
  before = st(h).note || ""
  const field = Object.assign(document.createElement("input"), { className: "note-in", value: before,
    placeholder: `a note on ${c.querySelector(".rail").textContent}; ↵ keeps it, Esc drops the edit` })
  field.setAttribute("aria-label", "note")
  // kept as typed, so a crash loses nothing; it belongs to the card it was opened on whatever moves
  field.addEventListener("input", () => { state.staged[h] = { ...st(h), note: field.value.trim() }; if (!field.value.trim()) stage(h, { note: null }); else persist() })
  field.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== "Escape") return
    e.preventDefault()
    e.stopPropagation()
    noting = null
    stage(h, { note: e.key === "Enter" ? field.value.trim() : before })
    c.focus({ preventScroll: true })
  })
  field.addEventListener("blur", () => { if (noting === h) { noting = null; stage(h, { note: field.value.trim() }) } })
  out.hidden = false
  out.replaceChildren(field)
  field.focus()
}

const send = async () => {
  if (!batch() && !words()) return say("nothing staged: nothing to send")
  if (!hub) { await write(batch()); return say("no hub frames this page: the batch is copied, to paste into the session") }
  const r = await hub.send(window)
  if (!r.ok) say(`not sent: ${r.error}`)
}

// A key that acts on the band; false where it is not the band's, so the page's own takes it.
const bandKey = (key) => {
  if (reviewing) {
    if (key === "Enter") { send(); return true }
    if (key === "Escape" || key === "r") { reviewing = false; draw(); items()[at]?.focus({ preventScroll: true }); return true }
    if (key === "[" || key === "]") { showCard(key === "]" ? 0 : items().length - 1); return true }
    return false
  }
  const list = items(), c = list[at]
  if (key === "Escape") { leaveBand(); return true }
  if (key === "]" || key === "[") { showCard(Math.max(0, Math.min(list.length - 1, at + (key === "]" ? 1 : -1)))); return true }
  if (key === "r") { reviewing = true; draw(); review.focus({ preventScroll: true }); return true }  // the card it hid had the focus
  if (!c) return false
  const h = c.dataset.handle, kind = c.dataset.kind
  if ((key === "o" || (key === "Enter" && kind === "look")) && c.querySelector("a.open")) { c.querySelector("a.open").click(); return true }
  if (!loaded && /^[a-z]$|^Enter$/.test(key)) { say("what you staged is still being read"); return true }
  if (kind === "decide" && key.length === 1 && (c.dataset.options || "").includes(key)) { toggle(h, "pick", key); return true }
  switch (key) {
    case "Enter": case "p":
      if (kind !== "decide") return key === "Enter"  // never the turn's, from a card
      if (!c.dataset.pick) { say(`${c.querySelector(".rail").textContent} carries no pick: answer it with n`); return true }
      if (key === "p") toggle(h, "pick", c.dataset.pick)
      else stage(h, { pick: c.dataset.pick })
      return true
    case "d": case "x": if (kind !== "do") return false; toggle(h, "act", key === "d" ? "done" : "dismissed"); return true
    case "s": if (kind !== "look") return false; see(h); return true
    case "n": note(c); return true
    case "u": stage(h, { pick: null, act: null, note: null }); return true
  }
  return false
}
if (waiting) {
  waiting.addEventListener("click", (e) => {
    const k = e.target.closest("[data-key]")
    if (k) { e.preventDefault(); bandKey(k.dataset.key); return }
    const row = e.target.closest("tr[data-option]"), c = e.target.closest(".card")
    if (row && c) toggle(c.dataset.handle, "pick", row.dataset.option)
  })
  // an artefact opened from its card, by a click or by o, is seen
  waiting.addEventListener("click", (e) => {
    const c = e.target.closest(".card.look")
    if (c && e.target.closest("a.open")) see(c.dataset.handle, true)
  }, true)
}
draw()

const sheetToggle = document.getElementById("sheet-toggle")
const sheet = (on = !document.body.classList.contains("sheet-open")) => {
  document.body.classList.toggle("sheet-open", on)
  sheetToggle.setAttribute("aria-expanded", on)
}
sheetToggle.addEventListener("click", () => sheet())
document.addEventListener("click", (e) => {
  if (document.body.classList.contains("sheet-open") && !column.contains(e.target) && !sheetToggle.contains(e.target)) sheet(false)
})

// ---- links within the page: a turn opens first, a waiting question opens in the band

const reveal = (id, how) => {
  const el = id && document.getElementById(id)
  if (!el) return
  sheet(false)
  const n = items().indexOf(el)
  if (n >= 0) { showCard(n); return }
  if (!pane.contains(el)) return
  const turn = el.closest("details.turn")
  if (turn) turn.open = true
  scrollTo(offsetIn(el) - MARGIN, how)
  const b = el.closest("[data-block]")
  if (b) { cur = blocks.indexOf(b); mark() }
}
document.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest('a[href^="#"]')
  if (!a) return
  e.preventDefault()
  history.replaceState(null, "", a.getAttribute("href"))
  reveal(a.getAttribute("href").slice(1))
})

// ---- the reader's place, kept across a reload
// The hub reloads the page each time a turn renders. Before it unloads, the page saves the block at
// the top of the pane and the offset into it, the open turns and the rest of what the reader set,
// and sets them again once reloaded. A reader who had the newest turn in view was caught up, and
// follows a turn that arrived above it to the top; one reading further back stays where they
// were. A reload never replays the fragment a link left in the address; only a navigation that
// arrives with one reveals it.

history.scrollRestoration = "manual"
const KEY = "session-page:" + document.getElementById("session-id").dataset.copy
const place = () => {
  const b = atTop()
  return {
    top: pane.scrollTop <= 1,
    newest: blocks.length ? blocks[0].id : null,
    caughtUp: blocks.length > 0 && blocks[0].getBoundingClientRect().bottom > pane.getBoundingClientRect().top + MARGIN,
    anchor: b ? b.id : null,
    into: b ? pane.getBoundingClientRect().top - b.getBoundingClientRect().top : 0,
    turns: turns.map((t) => t.id),
    open: turns.filter((t) => t.open).map((t) => t.id),
    cur: blocks[cur] ? blocks[cur].id : null,
    seen,
    card: items()[at] ? items()[at].id : null,
    band: waiting ? !waiting.classList.contains("collapsed") : true,
  }
}
const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(place())) } catch {} }
addEventListener("pagehide", save)
document.addEventListener("visibilitychange", () => { if (document.hidden) save() })

const restore = (s) => {
  // a turn the save did not know is new, and stays as rendered
  const known = new Set(s.turns), open = new Set(s.open)
  turns.forEach((t) => { if (known.has(t.id)) t.open = open.has(t.id) })
  const follows = s.caughtUp && blocks.length > 0 && blocks[0].id !== s.newest
  cur = s.cur && !follows ? blocks.findIndex((b) => b.id === s.cur) : -1
  mark()
  if (waiting) {
    const n = items().findIndex((c) => c.id === s.card)
    if (n >= 0) { at = n; draw() }
    band(s.band)
  }
  const anchor = s.anchor && document.getElementById(s.anchor)
  const go = () => { pane.scrollTop = follows || s.top || !anchor ? 0 : offsetIn(anchor) + s.into; reach() }
  go()
  // the web fonts land after the first layout and move every block: until the reader moves, the place is set again
  let moved = false
  for (const ev of ["wheel", "touchstart", "keydown", "mousedown"]) addEventListener(ev, () => (moved = true), { once: true, capture: true })
  document.fonts.ready.then(() => { if (!moved) go() })
  addEventListener("load", () => { if (!moved) go() })
}

let saved = null
try { saved = JSON.parse(sessionStorage.getItem(KEY)) } catch {}
seen = saved ? saved.seen : null
const arrival = performance.getEntriesByType("navigation")[0]
if (location.hash && (!arrival || arrival.type === "navigate")) reveal(location.hash.slice(1), "auto")
else if (saved) restore(saved)
reach()
refade()

// ---- a turn by its number: t, then the digits it shows

let typed = null  // the digits typed after t, while a turn is being named
const numbers = turns.map((t) => t.id.slice(1))
const forms = (key) => [key, String(+key)]  // 07 is typed as 07 or as 7
const goTo = (key) => {
  typed = null
  const t = document.getElementById("t" + key)
  t.open = true
  focusBlock(blocks.indexOf(t))
  say(`turn ${key}`)
}
// a turn named by the digits so far, and whether a longer number still starts with them
const named = () => numbers.find((k) => forms(k).includes(typed))
const longer = () => numbers.some((k) => forms(k).some((f) => f.length > typed.length && f.startsWith(typed)))
const byNumber = (e) => {
  if (/^[0-9]$/.test(e.key)) typed += e.key
  else if (e.key === "Backspace") typed = typed.slice(0, -1)
  else if (e.key === "Enter") {
    const key = named()
    if (key) goTo(key)
    else { say(`no turn ${typed}`); typed = null }
    return true
  } else {
    typed = null
    say("")
    return e.key === "Escape"
  }
  const key = named()
  if (key && !longer()) goTo(key)
  else if (!key && !longer()) { say(`no turn ${typed}`); typed = null }
  else say(`turn ${typed}…`, true)
  return true
}

// ---- copying

// "copied" rises over the element a click copied, and fades
const copied = (el) => {
  const r = el.getBoundingClientRect()
  const tip = Object.assign(document.createElement("span"), { className: "copied-tip", textContent: "copied" })
  Object.assign(tip.style, { left: `${r.left + r.width / 2}px`, top: `${r.top - 4}px` })
  document.body.append(tip)
  tip.addEventListener("animationend", () => tip.remove())
}
const write = async (text, el) => {
  try { await navigator.clipboard.writeText(text) }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text })
    document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove()
  }
  if (el) copied(el)
}
const resume = document.getElementById("resume")
const copy = () => write(resume.dataset.cmd, resume)
resume.addEventListener("click", copy)
const id = document.getElementById("session-id")
id.addEventListener("click", () => write(id.dataset.copy, id))
// a code block's button copies its code short of the newline that ends it, so a command pasted
// into a terminal waits for Enter rather than running
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".copy-code")
  if (b) write(b.parentElement.querySelector("pre").textContent.replace(/\n$/, ""), b)
})
// a turn's button copies its record as written, as y does for the cursor's turn, and Y every record of the
// session; a click on the button, which sits in the turn's summary, opens and closes nothing
const sources = JSON.parse(document.getElementById("sources").textContent)
const copyTurn = (b) => {
  if (!b) { say("no turn yet"); return }
  write(sources[b.id], b.querySelector(".copy-turn"))
  say(`copied ${b.matches(".chat") ? "the chat turn" : "turn " + b.id.slice(1)} as markdown`)
}
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".copy-turn")
  if (b) { e.preventDefault(); copyTurn(b.closest("[data-block]")) }
})
// a click on a path opens the file, and the browser's own copy gives its file:// URL, so c copies
// the path under the pointer, or the one Tab focused, as the turn shows it
const pathLink = (el) => el && el.closest && el.closest("a.path")
const pathAt = () => document.querySelector("a.path:hover") || pathLink(document.activeElement)
let hint = null
const hideHint = () => { if (hint) { hint.remove(); hint = null } }
const showHint = (a) => {
  if (hint && hint.path === a) return
  hideHint()
  const r = [...a.getClientRects()].at(-1)  // under the last line of a path that wraps
  hint = Object.assign(document.createElement("span"), { className: "key-hint", path: a, innerHTML: "<kbd>c</kbd> copy" })
  Object.assign(hint.style, { left: `${r.left}px`, top: `${r.bottom + 4}px` })
  document.body.append(hint)
}
// mousemove rather than mouseover, so the hint a scroll took away comes back with the pointer's next move
document.addEventListener("mousemove", (e) => { const a = pathLink(e.target); if (a) showHint(a) })
document.addEventListener("mouseout", (e) => {
  const a = pathLink(e.target)
  if (a && !a.contains(e.relatedTarget) && document.activeElement !== a) hideHint()
})
document.addEventListener("focusin", (e) => { const a = pathLink(e.target); if (a) showHint(a) })
document.addEventListener("focusout", (e) => { const a = pathLink(e.target); if (a && !a.matches(":hover")) hideHint() })
addEventListener("scroll", hideHint, { capture: true, passive: true })

// ---- the keys

// a scrolling key where nothing that scrolls has the focus scrolls the turns' pane, which the window would have
const scrollByKey = (key) => {
  const page = pane.clientHeight * 0.85
  const by = { PageDown: page, " ": page, PageUp: -page, ArrowDown: 40, ArrowUp: -40 }[key]
  if (by !== undefined) pane.scrollBy({ top: by })
  else pane.scrollTop = key === "Home" ? 0 : pane.scrollHeight
}

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
  if (typed !== null && byNumber(e)) { e.preventDefault(); return }
  if (e.key === "?") { toggleHelp(); e.preventDefault(); return }
  if (inBand() && bandKey(e.key)) { e.preventDefault(); return }
  if (e.key === "Escape") { toggleHelp(false); sheet(false); return }
  if (nativeKey(e)) return
  if (SCROLLING_KEYS.has(e.key)) {
    follow = "scroll"
    if (!(e.target.closest && e.target.closest(".pane, .column, .waiting"))) { scrollByKey(e.key); e.preventDefault() }
    return
  }
  if (e.key === "g") { gg(() => { scrollTo(0); cur = -1; mark(); document.activeElement.blur() }); return }
  const focused = blocks[cur]
  switch (e.key) {
    case "j": focusBlock(cur + 1); break
    case "k": focusBlock(cur < 0 ? 0 : cur - 1); break
    case "G": focusBlock(blocks.length - 1); break
    case "n": toNewest(); break
    case "t": if (numbers.length) { typed = ""; say("turn …", true) } break
    case "[": case "]": if (items().length) showCard(at); break
    case "q": if (waiting) band(); break
    case "o": case "Enter": if (focused && focused.matches("details")) focused.open = !focused.open; break
    case "O": { const open = !turns.every((t) => t.open); turns.forEach((t) => (t.open = open)); break }
    case "R": copy(); break
    case "y": copyTurn(focused || blocks[0]); break
    case "Y": if (blocks.length) { write(sources.session); say("copied the session as markdown") } else say("no turn yet"); break
    case "c": { const a = pathAt(); if (a) write(a.textContent, a); else say("no path under the pointer"); break }
    default: {
      if (!/^[1-9]$/.test(e.key)) return
      const turn = focused && focused.matches("details.turn") ? focused : turns[0]
      const g = group(turn)
      const link = g && g.querySelectorAll("a[data-artefact]")[+e.key - 1]
      if (link) link.click()  // a click, so whatever handles one on the page handles the key too
      else say(`turn ${turn ? turn.id.slice(1) : ""} has no artefact ${e.key}`)
    }
  }
  e.preventDefault()
})
