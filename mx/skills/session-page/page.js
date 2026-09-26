// The session page's keys, diffview's where diffview has the move; `?` on the page lists them.
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

// diffview's gg: a first g arms, a second within half a second goes to the top
let gArmed = false, gTimer = null
const gg = (go) => {
  if (gArmed) { clearTimeout(gTimer); gArmed = false; go() }
  else { gArmed = true; gTimer = setTimeout(() => (gArmed = false), 500) }
}
const typing = (e) => e.target.matches && e.target.matches("input, textarea, select, [contenteditable]")
const nativeKey = (e) => (e.key === "Enter" || e.key === " ") && e.target.closest && e.target.closest("button, a, summary")

const blocks = [...document.querySelectorAll("[data-block]")]
const turns = blocks.filter((b) => b.matches(".turn"))
let cur = -1
const mark = () => blocks.forEach((b, n) => b.classList.toggle("cur", n === cur))
const focusBlock = (i) => {
  if (!blocks.length) return
  cur = Math.max(0, Math.min(blocks.length - 1, i))
  mark()
  const b = blocks[cur]
  ;(b.matches("details") ? b.querySelector(":scope > summary") : b).focus({ preventScroll: true })
  b.scrollIntoView({ block: "start", behavior: behavior() })
}
document.addEventListener("focusin", (e) => {
  const b = e.target.closest && e.target.closest("[data-block]")
  if (b) { cur = blocks.indexOf(b); mark() }
})

// a link to a question or turn inside a closed turn opens that turn first
const reveal = (id) => {
  const el = id && document.getElementById(id)
  if (!el) return
  const turn = el.closest("details.turn")
  if (turn) turn.open = true
  el.scrollIntoView({ block: "start", behavior: behavior() })
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
if (location.hash) reveal(location.hash.slice(1))

const toast = document.getElementById("toast")
let toastTimer = null
const say = (text) => {
  toast.textContent = text
  toast.classList.add("on")
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => toast.classList.remove("on"), 2200)
}
const resume = document.getElementById("resume")
const copy = async () => {
  const cmd = resume.dataset.cmd
  try { await navigator.clipboard.writeText(cmd) }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: cmd })
    document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove()
  }
  resume.classList.add("copied")
  resume.querySelector("span").textContent = "copied"
  say("copied: " + cmd)
  setTimeout(() => { resume.classList.remove("copied"); resume.querySelector("span").textContent = "copy resume command" }, 1600)
}
resume.addEventListener("click", copy)

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
  if (e.key === "?") { toggleHelp(); e.preventDefault(); return }
  if (e.key === "Escape") { toggleHelp(false); return }
  if (nativeKey(e)) return
  if (e.key === "g") { gg(() => { window.scrollTo({ top: 0, behavior: behavior() }); cur = -1; mark(); document.activeElement.blur() }); return }
  const focused = blocks[cur]
  switch (e.key) {
    case "j": focusBlock(cur + 1); break
    case "k": focusBlock(cur < 0 ? 0 : cur - 1); break
    case "G": focusBlock(blocks.length - 1); break
    case "o": case "Enter": if (focused && focused.matches("details")) focused.open = !focused.open; break
    case "O": { const open = !turns.every((t) => t.open); turns.forEach((t) => (t.open = open)); break }
    case "y": copy(); break
    default: {
      if (!/^[1-9]$/.test(e.key)) return
      const turn = focused && focused.matches(".turn") ? focused : turns[0]
      const link = turn && turn.querySelectorAll("a.link")[+e.key - 1]
      if (link) window.open(link.href, "_blank", "noopener")
      else say(`turn ${turn ? turn.dataset.record : ""} has no link ${e.key}`)
    }
  }
  e.preventDefault()
})
