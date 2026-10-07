// The session page's keys, the same as diffview's where diffview has one; `?` on the page lists them.
// The window never scrolls: the turns scroll in their own pane, and so do the timeline and the
// questions' band, so every scroll here targets one of them.
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
const intro = document.querySelector(".intro")
const waiting = document.getElementById("open-questions")
const questions = waiting ? [...waiting.querySelectorAll(".q")] : []
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
// a scroll inside `box` that brings `el` into its view, a third of the way down, where it is out of it
const keepInView = (box, el, head = 0) => {
  const b = box.getBoundingClientRect(), r = el.getBoundingClientRect()
  if (r.top < b.top + head || r.bottom > b.bottom) box.scrollTop += r.top - b.top - head - (box.clientHeight - head) / 3
}

let cur = -1
// the cursor's turn is marked in the timeline too, and kept in the timeline's view
const group = (b) => (b && b.matches("details.turn") ? document.getElementById("a" + b.id.slice(1)) : null)
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

// ---- the control to the newest turn: marked while a turn is in that the reader has not reached

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
  if (turns[0]) turns[0].open = true
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
  faded.push(update)
}
const refade = () => requestAnimationFrame(() => faded.forEach((u) => u()))
fade(pane)
fade(column, columnHead)
if (waiting) fade(waiting, waiting.querySelector(".divider"))
waiting && waiting.querySelectorAll(".q-body").forEach((b) => fade(b))

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

// ---- the title's fold, the questions' accordion, the timeline's sheet

const unfold = document.getElementById("unfold")
const brief = (on = !intro.classList.contains("unfolded")) => {
  intro.classList.toggle("unfolded", on)
  unfold.setAttribute("aria-expanded", on)
  refade()
}
unfold.addEventListener("click", () => brief())

let openQ = questions.findIndex((q) => !q.classList.contains("folded"))
const foldBand = document.getElementById("fold-band")
const band = (on = waiting.classList.contains("collapsed")) => {
  waiting.classList.toggle("collapsed", !on)
  foldBand.setAttribute("aria-expanded", on)
  foldBand.firstChild.textContent = on ? "fold " : "show "
  refade()
}
const showQuestion = (i) => {
  openQ = i
  questions.forEach((q, n) => q.classList.toggle("folded", n !== i))
  if (i >= 0) { band(true); keepInView(waiting, questions[i], waiting.querySelector(".divider").offsetHeight) }
  refade()
}
questions.forEach((q, i) => q.addEventListener("click", (e) => {
  if (e.target.closest("a")) return
  if (q.classList.contains("folded")) showQuestion(i)
  else if (e.target.closest("h3")) showQuestion(-1)
}))
if (foldBand) foldBand.addEventListener("click", () => band())

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
  const q = questions.indexOf(el)
  if (q >= 0) { showQuestion(q); return }
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
// and sets them again once reloaded. A reload never replays the fragment a link left in the
// address; only a navigation that arrives with one reveals it.

history.scrollRestoration = "manual"
const KEY = "session-page:" + document.getElementById("session-id").dataset.copy
const place = () => {
  const b = atTop()
  return {
    top: pane.scrollTop <= 1,
    anchor: b ? b.id : null,
    into: b ? pane.getBoundingClientRect().top - b.getBoundingClientRect().top : 0,
    turns: turns.map((t) => t.id),
    open: turns.filter((t) => t.open).map((t) => t.id),
    cur: blocks[cur] ? blocks[cur].id : null,
    seen,
    question: questions[openQ] ? questions[openQ].id : null,
    band: waiting ? !waiting.classList.contains("collapsed") : true,
    brief: intro.classList.contains("unfolded"),
  }
}
const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify(place())) } catch {} }
addEventListener("pagehide", save)
document.addEventListener("visibilitychange", () => { if (document.hidden) save() })

const restore = (s) => {
  // a turn the save did not know is new, and stays as rendered
  const known = new Set(s.turns), open = new Set(s.open)
  turns.forEach((t) => { if (known.has(t.id)) t.open = open.has(t.id) })
  cur = s.cur ? blocks.findIndex((b) => b.id === s.cur) : -1
  mark()
  if (waiting) {
    const q = questions.findIndex((x) => x.id === s.question)
    if (q >= 0 || s.question === null) showQuestion(q)
    band(s.band)
  }
  brief(s.brief)
  const anchor = s.anchor && document.getElementById(s.anchor)
  const go = () => { pane.scrollTop = s.top || !anchor ? 0 : offsetIn(anchor) + s.into; reach() }
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

const write = async (text) => {
  try { await navigator.clipboard.writeText(text) }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text })
    document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove()
  }
  say("copied: " + text)
}
const resume = document.getElementById("resume")
const copy = async () => {
  await write(resume.dataset.cmd)
  resume.classList.add("copied")
  resume.querySelector("span").textContent = "copied"
  setTimeout(() => { resume.classList.remove("copied"); resume.querySelector("span").textContent = "copy resume command" }, 1600)
}
resume.addEventListener("click", copy)
const id = document.getElementById("session-id")
id.addEventListener("click", () => write(id.dataset.copy))

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
    case "[": if (questions.length) showQuestion(Math.max(0, (openQ < 0 ? questions.length : openQ) - 1)); break
    case "]": if (questions.length) showQuestion(Math.min(questions.length - 1, openQ + 1)); break
    case "q": if (waiting) band(); break
    case "o": case "Enter": if (focused && focused.matches("details")) focused.open = !focused.open; break
    case "O": { const open = !turns.every((t) => t.open); turns.forEach((t) => (t.open = open)); break }
    case "y": copy(); break
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
