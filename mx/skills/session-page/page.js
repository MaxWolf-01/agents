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
  setView("turns")
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
if (waiting) fade(waiting, waiting.querySelector(".t-head"))

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

// ---- the tasks: what waits on the reader, each answer staged, the batch sent as one message
// Each item is a row the renderer wrote, a question's and a to-do's with a card in the column's
// dialog, which opens one card at a time. The keys go to the tasks while the focus is in them ([ and ]
// put it there). What is staged is kept as the reader stages it: by the hub tab the page sits in,
// through the `hubWaiting` the container hub's tab defines (dotfiles' bin/container-hub.html), which
// also sends the batch; or, where no hub frames the page, in this browser's storage, and the review
// then copies the batch instead of sending it. Nothing reaches the session but by a send from the review.

const dialog = document.getElementById("card-dialog"), review = document.getElementById("review")
const rows = waiting ? [...waiting.querySelectorAll(".t-row[data-handle]")] : []
const cardOf = (row) => (row && row.dataset.card ? document.getElementById(row.dataset.card) : null)
const hub = (() => { try { return parent !== window && parent.hubWaiting && parent.hubWaiting.holds(window) ? parent.hubWaiting : null } catch { return null } })()
const STAGED = "session-page:staged:" + document.getElementById("session-id").dataset.copy
// staged: each item's answer by its handle, {pick, act, note}; seen: the artefacts marked seen, which
// go in the batch; sent: when each item went in a batch, which keeps it off the tasks until a turn
// that ended after the send is on the page
let state = { staged: {}, seen: [], sent: {} }
let loaded = !waiting, at = -1, open = false, reviewing = false, noting = null, before = "", pending = null
const handles = new Set(rows.map((r) => r.dataset.handle))

const items = () => rows.filter((r) => !state.sent[r.dataset.handle])
const carded = () => items().filter((r) => r.dataset.card)
const current = () => items()[at] || null
const st = (h) => state.staged[h] || {}
const seenOf = (h) => state.seen.includes(h)
const answer = (h) => [st(h).pick || st(h).act || (seenOf(h) ? "seen" : ""), st(h).note].filter(Boolean).join(", ")
const line = (h) => `${h}: ${answer(h)}`
const goes = (h) => !!(state.staged[h] || seenOf(h))
// What was staged on an item this render no longer shows (a question settled meanwhile): kept until
// it is sent, and sent after the rows' lines.
const orphans = () => [...new Set([...Object.keys(state.staged), ...state.seen])].filter((h) => !handles.has(h))
const batch = () => [...items().map((r) => r.dataset.handle).filter(goes), ...orphans()].map(line).join("\n")
const words = () => (hub ? hub.words(window) : "").trim()

let saving = Promise.resolve()
// Each save waits for the one before it, so the hub keeps the newest.
const persist = () => {
  const doc = JSON.parse(JSON.stringify(state))
  if (!hub) {
    try { localStorage.setItem(STAGED, JSON.stringify(doc)) } catch (e) { say(`not kept: this browser's storage refused it (${e.name})`) }
    return
  }
  saving = saving.then(() => hub.save(window, doc)).then((r) => { if (!r.ok) say(`not kept: ${r.error}`) }, () => say("not kept: the hub tab did not answer"))
}
// `redraw` false leaves the row as it is, for the note field typed into
const stage = (h, patch, redraw = true) => {
  const s = { ...st(h), ...patch }
  Object.keys(s).forEach((k) => { if (!s[k]) delete s[k] })
  if (Object.keys(s).length) state.staged[h] = s
  else delete state.staged[h]
  persist()
  if (redraw) draw()
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
  if (!doc) return
  state = { staged: doc.staged || {}, seen: (doc.seen || []).filter((h) => handles.has(h)),
            sent: Object.fromEntries(Object.entries(doc.sent || {}).filter(([h, t]) => handles.has(h) && !ended.some((e) => e > t))) }
}
const read = !waiting ? Promise.resolve()
  : (hub ? Promise.resolve().then(() => hub.load(window)).then((r) => { if (!r.ok) throw new Error(r.error); return r.staged })
         : Promise.resolve().then(() => JSON.parse(localStorage.getItem(STAGED) || "null")))
      .then(adopt, (e) => say(`what you staged could not be read: ${e.message}`))
      .finally(() => {
        loaded = true
        // a card the reload or a link named, found among the items once the sent ones are known
        if (pending) { const n = items().findIndex((r) => r.dataset.card === pending); if (n >= 0) { at = n; open = true } }
        pending = null
        draw()
        if (hub) hub.restaged(window)
      })

// the hub tab's side: the batch a send from the review carries, and the lines that went, which leave the tasks
window.waitingBatch = () => (loaded ? batch() : "")
window.waitingStaged = () => (loaded ? items().filter((r) => goes(r.dataset.handle)).length + orphans().length : 0)
window.waitingSent = (text) => read.then(() => {
  const sent = new Set(text.split("\n")), now = Date.now(), keys = inBand()
  for (const h of new Set([...Object.keys(state.staged), ...state.seen])) if (sent.has(line(h))) {
    if (handles.has(h)) state.sent[h] = now
    delete state.staged[h]
    state.seen = state.seen.filter((x) => x !== h)
  }
  persist()
  // back to the first item still waiting, the keys kept in the tasks where the review had them
  reviewing = false
  open = false
  at = 0
  draw()
  waiting.scrollTop = 0
  if (keys) waiting.focus({ preventScroll: true })
})
// the review is open: the box's Enter sends what it shows, the batch with the box's words below it
window.waitingReviewing = () => reviewing
// the box's words changed as the user typed there: the review's message shows them, the rest of it left as it is
window.waitingWords = () => { if (reviewing) review.querySelector(".message").outerHTML = message() }
// a reload under a note being typed would take the field from under the reader's fingers
window.reloadWouldLose = () => noting !== null

const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;")
const staged = (row) => {
  const h = row.dataset.handle, s = st(h), c = cardOf(row)
  const option = s.pick && c && c.querySelector(`tr[data-option="${s.pick}"] td:nth-child(2)`)
  const what = (option ? `${s.pick} · ${option.textContent.trim()}` : s.pick) || s.act || (seenOf(h) ? "seen" : "")
  return what || s.note ? `staged: ${[what, s.note && `note: ${s.note}`].filter(Boolean).join(" · ")}` : ""
}
const drawRow = (row, n) => {
  const h = row.dataset.handle, s = st(h)
  row.hidden = !!state.sent[h]
  row.classList.toggle("at", n === at)
  row.classList.toggle("st", goes(h))
  row.querySelectorAll(".pill").forEach((p) => p.classList.toggle("on", p.dataset.pick === s.pick))
  row.querySelectorAll("[data-act=done], [data-act=dismissed]").forEach((b) => b.classList.toggle("on", b.dataset.act === s.act))
  const noteButton = row.querySelector("[data-act=note]")
  noteButton.classList.toggle("kept", !!s.note)
  noteButton.dataset.tip = s.note ? `Your note\n${s.note}` : "Add a note\nn works from anywhere on the page."
  const seenButton = row.querySelector(".seen-btn")
  if (seenButton) {
    const on = seenOf(h)
    seenButton.classList.toggle("on", on)
    seenButton.setAttribute("aria-pressed", on)
    seenButton.querySelector("span").textContent = on ? "Seen" : "Mark seen"
    seenButton.dataset.tip = on ? "Marked seen\nIt stays until you send, so you can still undo it." : "Mark it seen\nIt leaves this list when you send, and the agent is told."
    // the timeline marks it too, until the send takes it off the tasks
    const target = row.querySelector("a[data-artefact]").dataset.artefact
    column.querySelectorAll("a[data-artefact]").forEach((a) => { if (a.dataset.artefact === target) a.closest("li").classList.toggle("seen-staged", on) })
  }
}
const drawCard = (c, row) => {
  const h = row.dataset.handle, s = st(h)
  c.querySelectorAll("tr[data-option]").forEach((tr) => tr.classList.toggle("chosen", tr.dataset.option === s.pick))
  const out = c.querySelector(".staged")
  if (noting === h) return
  out.textContent = staged(row)
  out.hidden = !out.textContent
}
const draw = () => {
  if (!waiting) return
  const list = items()
  at = Math.min(at, list.length - 1)
  rows.forEach((r) => drawRow(r, list.indexOf(r)))
  const c = cardOf(current())
  dialog.querySelectorAll(".card").forEach((card) => { card.hidden = reviewing || card !== c })
  dialog.hidden = !(open && (reviewing || c))
  if (c) drawCard(c, current())
  const n = list.filter((r) => goes(r.dataset.handle)).length + orphans().length
  const badge = waiting.querySelector(".rv b") || waiting.querySelector(".rv").appendChild(Object.assign(document.createElement("b"), { className: "v-num" }))
  badge.textContent = n || ""
  review.hidden = !reviewing
  if (reviewing) drawReview(list)
  refade()
}
const message = () => {
  const text = [batch(), words()].filter(Boolean).join("\n\n")
  return text ? `<pre class="message">${esc(text)}</pre>` : `<p class="v-small empty message">Nothing staged yet.</p>`
}
const drawReview = (list) => {
  const left = list.filter((r) => !goes(r.dataset.handle))
  const named = (r) => (r.dataset.kind === "look" ? r.querySelector(".t-h").textContent : r.dataset.handle)
  const stays = !left.length ? `<p class="left-out v-small">Every item has an answer, or was seen.</p>`
    : `<p class="left-out v-small">Not answered, so they stay: ${esc(left.map(named).join(", "))}</p>`
  const gone = orphans()
  review.innerHTML = `<h3 class="v-h2">The batch, as the session gets it</h3>` + message() +
    (gone.length ? `<p class="left-out v-small">Staged on items this page no longer shows, and sent with the rest: ${esc(gone.join(", "))}.</p>` : "") +
    stays +
    `<p class="keys-row v-meta"><button type="button" class="key" data-key="Enter"><kbd>↵</kbd> ${hub ? "send" : "copy it: no hub frames this page to send it"}</button>` +
    `<button type="button" class="key" data-key="Escape"><kbd>Esc</kbd> back</button></p>`
}

const inBand = () => !!waiting && (waiting.contains(document.activeElement) || open)
// the tasks take the keys: the row in focus is marked, and kept in the column's view
const focusRow = (n) => {
  const list = items()
  if (!list.length) return
  at = Math.max(0, Math.min(list.length - 1, n))
  if (!waiting.contains(document.activeElement)) waiting.focus({ preventScroll: true })
  draw()
  keepInView(waiting, list[at], waiting.querySelector(".t-head").offsetHeight)
}
const openCard = (n) => {
  const list = items()
  if (!list[n] || !list[n].dataset.card) return false
  at = n
  open = true
  reviewing = false
  setView("tasks")
  draw()
  cardOf(list[at]).focus({ preventScroll: true })
  return true
}
const closeDialog = () => { open = false; reviewing = false; draw(); waiting.focus({ preventScroll: true }) }
const openReview = () => {
  open = true
  reviewing = true
  setView("tasks")
  draw()
  review.focus({ preventScroll: true })
}

// q and the head's chevron fold the tasks to their head, which gives the timeline their room
const foldButton = document.getElementById("fold-tasks")
const fold = (on = !waiting.classList.contains("folded")) => {
  waiting.classList.toggle("folded", on)
  foldButton.setAttribute("aria-expanded", !on)
  foldButton.setAttribute("aria-label", on ? "show the tasks" : "fold the tasks")
  foldButton.dataset.tip = on ? "Show the tasks" : "Fold the tasks\nThe timeline gets the room."
  refade()
}

// a note on the row, in a field under it, or in the open card's
const note = (row) => {
  const h = row.dataset.handle, c = open && cardOf(row)
  noting = h
  before = st(h).note || ""
  const field = Object.assign(document.createElement("input"), { className: "note-in", value: before,
    placeholder: `a note on ${row.dataset.kind === "look" ? "it" : h}; ↵ keeps it, Esc drops the edit` })
  field.setAttribute("aria-label", "note")
  const done = (keep) => {
    noting = null
    stage(h, { note: keep ? field.value.trim() : before })
    if (!c) field.remove()
    ;(c || waiting).focus({ preventScroll: true })
  }
  // kept as typed, so a crash loses nothing; it belongs to the item it was opened on whatever moves
  field.addEventListener("input", () => stage(h, { note: field.value.trim() }, false))
  field.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== "Escape") return
    e.preventDefault()
    e.stopPropagation()
    done(e.key === "Enter")
  })
  field.addEventListener("blur", () => { if (noting === h) done(true) })
  if (c) { const out = c.querySelector(".staged"); out.hidden = false; out.replaceChildren(field) }
  else { field.classList.add("t-note"); row.after(field) }
  field.focus()
}

const send = async () => {
  if (!batch() && !words()) return say("nothing staged: nothing to send")
  if (!hub) { await write(batch()); return say("no hub frames this page: the batch is copied, to paste into the session") }
  const r = await hub.send(window)
  if (!r.ok) say(`not sent: ${r.error}`)
}

// A key that acts on the tasks; false where it is not theirs, so the page's own takes it.
const bandKey = (key) => {
  if (reviewing) {
    if (key === "Enter") { send(); return true }
    if (key === "Escape" || key === "r") { reviewing = false; if (current() && current().dataset.card) openCard(at); else closeDialog(); return true }
    return false
  }
  const list = items(), row = current()
  if (key === "Escape") {
    if (open) closeDialog()
    else { document.activeElement.blur(); at = -1; draw(); if (blocks[cur]) focusBlock(cur) }
    return true
  }
  if (key === "]" || key === "[") {
    const step = key === "]" ? 1 : -1
    if (open) {
      const cs = carded(), here = cs.indexOf(row), to = cs[Math.max(0, Math.min(cs.length - 1, here + step))]
      if (to) openCard(list.indexOf(to))
    } else if (key === "[" && at <= 0) { at = 0; waiting.scrollTo({ top: 0, behavior: behavior() }); focusRow(0) }
    else focusRow(at + step)
    return true
  }
  if (key === "r") { openReview(); return true }
  if (!row) return false
  const h = row.dataset.handle, kind = row.dataset.kind
  if (key === "Enter") { if (!open && !openCard(at) && kind === "look") row.querySelector("a.open").click(); return true }
  if (key === "o") {
    const link = kind === "look" ? row.querySelector("a.open") : cardOf(row) && cardOf(row).querySelector("a.open")
    if (link) link.click()
    return true
  }
  if (!loaded && /^[a-z]$/.test(key)) { say("what you staged is still being read"); return true }
  if (kind === "decide" && key.length === 1 && (row.dataset.options || "").includes(key)) { toggle(h, "pick", key); return true }
  switch (key) {
    case "d": case "x": if (kind !== "do") return false; toggle(h, "act", key === "d" ? "done" : "dismissed"); return true
    case "s": if (kind !== "look") return false; see(h); return true
    case "n": note(row); return true
    case "u": stage(h, { pick: null, act: null, note: null }); if (kind === "look") see(h, false); return true
  }
  return false
}
const rowAct = (row, act) => {
  const h = row.dataset.handle
  at = items().indexOf(row)
  if (act === "note") note(row)
  else if (act === "seen") see(h)
  else toggle(h, "act", act)
}
// the tasks' clicks and the dialog's, which sits outside the column over the whole window
const onTasks = (e) => {
  const t = e.target, k = t.closest("[data-key]"), row = t.closest(".t-row"), act = t.closest("[data-act]"), c = t.closest(".card")
  if (t === dialog) { closeDialog(); return }
  if (k) { e.preventDefault(); bandKey(k.dataset.key); return }
  if (act && act.dataset.act === "work") { openCard(Math.max(0, items().findIndex((r) => r.dataset.card))); return }
  if (act && act.dataset.act === "review") { openReview(); return }
  if (act && act.dataset.act === "fold") { fold(); return }
  if (row && act) { e.preventDefault(); rowAct(row, act.dataset.act); return }
  if (row && t.closest(".pill")) { at = items().indexOf(row); toggle(row.dataset.handle, "pick", t.closest(".pill").dataset.pick); return }
  const option = t.closest("tr[data-option]")
  if (option && c) { const r = rows.find((x) => x.dataset.card === c.id); toggle(r.dataset.handle, "pick", option.dataset.option); return }
  // a row's tag or words open its card; a link in it, an artefact's or a ticket's, opens what it names
  if (row && !t.closest("a:not(.qt), button, input")) { e.preventDefault(); if (!openCard(items().indexOf(row))) focusRow(items().indexOf(row)) }
}
if (waiting) [waiting, dialog].forEach((el) => el.addEventListener("click", onTasks, true))
draw()

// ---- a turn under way: the tasks say so while one runs. The page is a file the hub reloads as each
// turn renders, so nothing tells it a turn began; it reads the live hook's file every few seconds.
const working = document.getElementById("working")
const liveSrc = document.getElementById("log-toggle").dataset.live
const poll = () => {
  if (document.hidden || !working) return
  const s = Object.assign(document.createElement("script"), { src: `${liveSrc}?${Date.now()}` })
  const show = () => {
    s.remove()
    const live = window.liveCalls
    working.hidden = !live
    if (live) working.querySelector(".t-txt").textContent = `A turn is running: ${live.prompt || "no prompt"}`.slice(0, 160)
  }
  s.onload = show
  s.onerror = () => { window.liveCalls = null; show() }
  document.head.append(s)
}
if (working) { poll(); setInterval(poll, 4000) }

// ---- a phone: the turns, or the tasks and the timeline, one at a time; the bar's button flips them
const viewToggle = document.getElementById("view-toggle")
const setView = (view) => {
  // the button shows where it goes
  document.body.dataset.view = view
  viewToggle.setAttribute("aria-label", view === "tasks" ? "the turns" : "the tasks and the timeline")
}
setView("tasks")
viewToggle.addEventListener("click", () => setView(document.body.dataset.view === "turns" ? "tasks" : "turns"))
// the tool calls of a turn, by a button on it, since l reaches them only from a keyboard
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".turn-log")
  if (!b) return
  e.preventDefault()
  e.stopPropagation()
  const block = b.closest("[data-block]")
  ;(block.matches("details") ? block.querySelector(":scope > summary") : block).focus({ preventScroll: true })
  const toggleLog = document.getElementById("log-toggle")
  if (toggleLog.getAttribute("aria-expanded") !== "true") toggleLog.click()
}, true)
// ---- links within the page: a turn opens first, a waiting question opens in the band

const reveal = (id, how) => {
  const el = id && document.getElementById(id)
  if (!el) return
  if (dialog && dialog.contains(el) && el.matches(".card")) {
    if (loaded) openCard(items().findIndex((r) => r.dataset.card === el.id))
    else pending = el.id
    return
  }
  if (!pane.contains(el)) return
  setView("turns")
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
    card: open && current() ? current().dataset.card : null,
    folded: !!waiting && waiting.classList.contains("folded"),
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
  if (waiting) { pending = s.card; fold(!!s.folded) }
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

// ---- tooltips

// An element's `data-tip` shows below it after half a second of hover, centred on it and kept inside the window: an
// overlay fixed to the window, so a pane that clips its overflow cannot cut it off.
const tipBox = Object.assign(document.createElement("div"), { className: "tip", role: "tooltip" })
document.body.append(tipBox)
let tipFor = null, tipTimer = null
const hideTip = () => { clearTimeout(tipTimer); tipFor = null; tipBox.classList.remove("on") }
document.addEventListener("pointermove", (e) => {
  const el = e.target.closest && e.target.closest("[data-tip]")
  if (el === tipFor) return
  hideTip()
  if (!el) return
  tipFor = el
  tipTimer = setTimeout(() => {
    if (!el.isConnected) return  // the log drew its steps again under the pointer
    // the first line is the tooltip's title, the rest what it says beneath
    const [first, ...rest] = el.dataset.tip.split("\n")
    tipBox.replaceChildren(Object.assign(document.createElement("b"), { textContent: first }), ...(rest.length ? ["\n" + rest.join("\n")] : []))
    const r = el.getBoundingClientRect(), w = tipBox.offsetWidth
    tipBox.style.left = `${Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2))}px`
    tipBox.style.top = `${r.bottom + 6}px`
    tipBox.classList.add("on")
  }, 500)
})
document.addEventListener("pointerout", (e) => { if (!e.relatedTarget) hideTip() })
document.addEventListener("scroll", hideTip, true)

// A tag's preview is a tooltip too: the renderer writes it as the link's title, which the browser
// would show in its own plain box, late.
document.querySelectorAll("a.qualified[title]").forEach((a) => { a.dataset.tip = a.title; a.removeAttribute("title") })

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
// c copies the link or code under the pointer, or the link Tab focused: a path written as code as the turn
// shows it, `:line` and all, since a click opens the file and the browser's own copy gives its file:// URL;
// any other link its target, a file on this machine as its path; code its text, short of the newline that
// ends a block. A link to a place on the page copies nothing of its own, only code inside it. A link out wins
// over code inside it, so a ticket's tag copies the same wherever the pointer sits on it.
const LINK = "a.path, a[href]:not([href^='#'])"
const copyable = (el) => el && el.closest ? el.closest(LINK) || el.closest("pre, code") : null
const copyText = (el) => {
  if (!el.matches("a") || el.matches(".path")) return el.textContent.replace(/\n$/, "")
  const url = new URL(el.href)
  return url.protocol === "file:" ? decodeURIComponent(url.pathname) : el.href
}
const copyableAt = () => copyable([...document.querySelectorAll(":hover")].at(-1)) || copyable(document.activeElement)
let hint = null
const hideHint = () => { if (hint) { hint.remove(); hint = null } }
const showHint = (el) => {
  if (hint && hint.over === el) return
  hideHint()
  const r = [...el.getClientRects()].at(-1)  // under the last line of a link that wraps
  hint = Object.assign(document.createElement("span"), { className: "key-hint", over: el, innerHTML: "<kbd>c</kbd> copy" })
  Object.assign(hint.style, { left: `${r.left}px`, top: `${r.bottom + 4}px` })
  document.body.append(hint)
}
// mousemove rather than mouseover, so the hint a scroll took away comes back with the pointer's next move
document.addEventListener("mousemove", (e) => { const el = copyable(e.target); if (el) showHint(el) })
document.addEventListener("mouseout", (e) => {
  const el = copyable(e.target)
  if (el && !el.contains(e.relatedTarget) && document.activeElement !== el) hideHint()
})
document.addEventListener("focusin", (e) => { const el = copyable(e.target); if (el) showHint(el) })
document.addEventListener("focusout", (e) => { const el = copyable(e.target); if (el && !el.matches(":hover")) hideHint() })
addEventListener("scroll", hideHint, { capture: true, passive: true })

// ---- the keys

// Ctrl+Alt held shows each control's key over it, so a control needs no key written on it. Any other
// key, a scroll or leaving the page takes them away: the hub's own keys are Ctrl+Alt and another key.
let overKeys = []
const hideKeys = () => { overKeys.forEach((k) => k.remove()); overKeys = [] }
const showKeys = () => {
  for (const el of document.querySelectorAll("[aria-keyshortcuts]")) {
    const r = el.getBoundingClientRect()
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) || r.bottom < 0 || r.top > innerHeight) continue
    const k = Object.assign(document.createElement("kbd"), { className: "key-over", textContent: el.getAttribute("aria-keyshortcuts") })
    Object.assign(k.style, { left: `${r.left + r.width / 2}px`, top: `${r.top + r.height / 2}px` })
    document.body.append(k)
    overKeys.push(k)
  }
}
addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.altKey && (e.key === "Control" || e.key === "Alt")) { if (!overKeys.length) showKeys() }
  else hideKeys()
}, true)
addEventListener("keyup", (e) => { if (e.key === "Control" || e.key === "Alt") hideKeys() }, true)
addEventListener("blur", hideKeys)
addEventListener("scroll", hideKeys, { capture: true, passive: true })

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
  if (e.key === "Escape") { toggleHelp(false); return }
  if (nativeKey(e)) return
  if (SCROLLING_KEYS.has(e.key)) {
    follow = "scroll"
    if (!(e.target.closest && e.target.closest(".pane, .column, .tasks"))) { scrollByKey(e.key); e.preventDefault() }
    return
  }
  if (e.key === "g") { gg(() => { scrollTo(0); cur = -1; mark(); document.activeElement.blur(); column.scrollTo({ top: 0, behavior: behavior() }) }); return }
  const focused = blocks[cur]
  switch (e.key) {
    case "j": focusBlock(cur + 1); break
    case "k": focusBlock(cur < 0 ? 0 : cur - 1); break
    case "G": focusBlock(blocks.length - 1); column.scrollTo({ top: column.scrollHeight, behavior: behavior() }); break
    case "N": toNewest(); break
    case "n": if (current()) note(current()); else say("no item in focus: ] picks one"); break
    case "t": if (numbers.length) { typed = ""; say("turn …", true) } break
    case "[": case "]": if (items().length) { fold(false); focusRow(at < 0 ? 0 : at) } break
    case "q": if (waiting) fold(); break
    case "r": if (waiting) openReview(); break
    case "Enter": if (focused && focused.matches("details")) focused.open = !focused.open; break
    case "o": { const open = !turns.every((t) => t.open); turns.forEach((t) => (t.open = open)); break }
    case "R": copy(); break
    case "y": copyTurn(focused || blocks[0]); break
    case "Y": if (blocks.length) { write(sources.session); say("copied the session as markdown") } else say("no turn yet"); break
    case "c": { const el = copyableAt(); if (el) write(copyText(el), el); else say("no link or code under the pointer"); break }
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
