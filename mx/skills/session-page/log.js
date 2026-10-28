// The tool-call log: a drawer on the right, over the timeline, showing what the focused turn did
// (page.js marks that turn's block .cur); with none focused, the turn under way's, else the newest
// turn's. `log l` in the bar or l opens and closes it, and Esc closes it. Tab, or a click on a
// step, hands the keys to the open log: j and k walk its steps, o and Enter open one, O opens or
// closes them all, and Tab hands the keys back to the turns. The steps live beside the
// page in tool-calls.js, which the first opening loads, with the highlighter; until then the page
// holds none of them. The turn under way's are in live-calls.js, which the live hook rewrites as
// each call starts and ends, and which the open log loads again every POLL. It runs after page.js
// in the same page, and uses its `pane`, `blocks` and `typing`.
(() => {
  const toggleButton = document.getElementById("log-toggle")
  const HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js"
  const HLJS_SRI = "sha384-RH2xi4eIQ/gjtbs9fUXM68sLSi99C7ZWBRX1vDrVv6GQXRibxXLbwO2NGZB74MbU"
  const CUT = 1500  // the characters of a request or a result a step shows until "show all"
  const POLL = 2000  // ms between two loads of the turn under way's calls, while the log is open

  const ICON = {
    command: '<path d="M4 17l6-5-6-5M12 19h8"/>',
    read: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    write: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
    web: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    subagent: '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17" cy="9" r="2"/><path d="M15 20a5 5 0 0 1 6-4.5"/>',
    thinking: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"/>',
    other: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5z"/>',
  }
  const NAMES = { command: "commands run", read: "files read or searched", write: "files written", web: "looks on the web",
    subagent: "subagents", thinking: "thoughts", other: "other tools" }
  const icon = (k) => `<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICON[k] || ICON.other}</svg>`
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c])
  const secs = (a, b) => (a && b ? Math.max(0, (Date.parse(b) - Date.parse(a)) / 1000) : null)
  const took = (s) => (s == null ? "" : s < 1 ? "<1s" : s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`)

  // ---- loading, once: the steps and the highlighter, each a script; a highlighter that fails to load leaves the code plain

  const script = (src, integrity) => new Promise((done, fail) => {
    const s = Object.assign(document.createElement("script"), { src, onload: done, onerror: fail })
    if (integrity) Object.assign(s, { integrity, crossOrigin: "anonymous" })
    document.head.append(s)
  })
  let loading = null
  const load = () => (loading ||= Promise.allSettled([script(toggleButton.dataset.src), script(HLJS, HLJS_SRI), loadLive()]))
  // the turn under way's calls as the file has them now; no file is no turn under way
  const loadLive = () => {
    const src = `${toggleButton.dataset.live}?${Date.now()}`
    return script(src).catch(() => (window.liveCalls = null))
      .finally(() => document.querySelectorAll(`script[src="${src}"]`).forEach((s) => s.remove()))
  }

  // ---- highlighting: a language by the file's extension, JSON pretty-printed

  const EXT = { py: "python", ts: "typescript", tsx: "typescript", js: "javascript", mjs: "javascript", jsx: "javascript", sh: "bash", bash: "bash",
    zsh: "bash", json: "json", jsonl: "json", md: "markdown", html: "xml", xml: "xml", svg: "xml", css: "css", scss: "scss", yaml: "yaml", yml: "yaml",
    toml: "ini", ini: "ini", rs: "rust", go: "go", c: "c", h: "c", cpp: "cpp", java: "java", kt: "kotlin", lua: "lua", sql: "sql", rb: "ruby",
    swift: "swift", mk: "makefile", nix: "nix", diff: "diff", patch: "diff" }
  const langOf = (path) => {
    const name = String(path || "").split("/").pop()
    if (name === "Makefile") return "makefile"
    return EXT[name.includes(".") ? name.split(".").pop().toLowerCase() : ""] || ""
  }
  const lit = (code, lang) => {
    if (lang && window.hljs && hljs.getLanguage(lang)) {
      try { return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value } catch {}
    }
    return esc(code)
  }
  const asJson = (text) => {
    const t = String(text).trim()
    if (!/^[[{]/.test(t)) return null
    try { return JSON.stringify(JSON.parse(t), null, 2) } catch { return null }
  }
  // a block cut at CUT keeps the whole in the step's data and shows it on "show all"
  let shownSteps = []
  const block = (code, lang, cls = "", whole = null) => {
    code = String(code)
    const long = code.length > CUT
    return `<pre class="code ${cls}" data-lang="${lang}"${long ? ` data-whole="${whole}"` : ""}><code>${lit(long ? code.slice(0, CUT) + "\n…" : code, lang)}</code></pre>` +
      (long ? `<button class="more" type="button">show all ${code.length.toLocaleString()} characters</button>` : "")
  }
  // a Read result's lines carry `   12→` in front, which the highlighter is spared
  const unnumbered = (text) => String(text).replace(/^ *\d+→/gm, "")

  // what a step asked for and what came back, each block named by a path into the step for "show all"
  const pieces = (s) => {
    const i = s.input, lang = langOf(i.file_path || i.notebook_path)
    const out = []
    if (s.tool === "Bash") out.push(["request", i.command || "", "bash", ""])
    else if (s.tool === "Edit") out.push(["old", i.old_string || "", lang, "del"], ["new", i.new_string || "", lang, "add"])
    else if (s.tool === "MultiEdit") (i.edits || []).forEach((e) => out.push(["old", e.old_string || "", lang, "del"], ["new", e.new_string || "", lang, "add"]))
    else if (s.tool === "Write") out.push(["request", i.content || "", lang, "add"])
    else if (s.tool !== "Read") out.push(["request", JSON.stringify(i, null, 2), "json", ""])
    const result = s.output || ""
    if (result) {
      const json = asJson(result)
      out.push(["result", json || (s.tool === "Read" ? unnumbered(result) : result), json ? "json" : s.tool === "Read" ? lang : "", s.failed ? "failed" : ""])
    }
    return out
  }
  // the step's line names the file; a Read of part of one says which part
  const where = (s) => {
    const i = s.input
    if (s.tool !== "Read" || !(i.offset || i.limit)) return ""
    return `<p class="path">${i.offset ? `from line ${i.offset}` : "from the top"}${i.limit ? ` · ${i.limit} lines` : ""}</p>`
  }
  const detail = (s, n) => where(s) + pieces(s).map(([label, code, lang, cls], k) =>
    (label === "result" ? `<p class="label">${s.failed ? "error" : "result"}</p>` : "") + block(code, lang, cls, `${n}.${k}`)).join("")

  // ---- the drawer

  const panel = Object.assign(document.createElement("aside"), { className: "log", id: "log" })
  panel.setAttribute("aria-label", "the focused turn's tool calls")
  document.body.append(panel)
  const cursor = () => blocks.find((b) => b.classList.contains("cur"))
  const focused = () => cursor() || blocks[0]
  // the turn under way shows where no turn is focused, or where the reader asked for it from the head
  let toLive = false, cursorWas
  const target = () => (window.liveCalls && (toLive || !cursor()) ? LIVE : focused())
  const LIVE = "live"
  const label = (b) => {
    if (b === LIVE) return `<span class="pulse" aria-hidden="true"></span>under way <span class="hl">· ${esc(window.liveCalls.prompt || "no prompt")}</span>`
    if (!b) return "no turn yet"
    const [name, about] = b.matches("details.turn") ? [`turn ${b.id.slice(1)}`, b.querySelector(".hl").textContent]
      : ["chat turn", b.querySelector(".date").textContent]
    return `${esc(name)} <span class="hl">· ${esc(about)}</span>`
  }
  let shownFor = null

  const running = (s) => `<span class="took running" data-at="${esc(s.at)}">${took(secs(s.at, new Date().toISOString()))}…</span>`
  const step = (s, n) => s.kind === "thinking"
    ? `<div class="step thinking" data-n="${n}"><button type="button">${icon("thinking")}<span class="subject">${esc(s.output)}</span></button></div>`
    : `<div class="step" data-n="${n}"><button type="button">${icon(s.kind)}<span class="verb">${esc(s.verb)}</span><span class="subject">${esc(s.subject)}</span>` +
      `${s.failed ? '<span class="failed" title="failed">✕</span>' : ""}${s.done ? `<span class="took">${took(secs(s.at, s.done))}</span>` : running(s)}</button></div>`

  // Drawn again over the same turn, as its calls come in, the log keeps the steps the reader opened
  // and where they scrolled to, and follows the newest call where they were at the end.
  function draw() {
    const was = panel.querySelector(".log-steps"), now = target()
    const kept = now === shownFor && was && { open: [...was.querySelectorAll(".step.open")].map((el) => +el.dataset.n),
      top: was.scrollTop, end: was.scrollTop + was.clientHeight >= was.scrollHeight - 4 }
    shownFor = now
    const steps = (shownFor === LIVE ? window.liveCalls.steps : window.toolCalls && shownFor && window.toolCalls[shownFor.id]) || []
    shownSteps = steps
    const tally = {}
    steps.forEach((s) => (tally[s.kind] = (tally[s.kind] || 0) + 1))
    const first = steps[0], last = steps[steps.length - 1]
    const span = first ? took(secs(first.at, last.done || last.at)) : ""
    const empty = shownFor === LIVE ? "no tool calls yet"
      : !window.toolCalls ? "the tool calls are not beside this page: the next turn's render writes them"
      : "no tool calls for this turn"
    const jump = shownFor !== LIVE && window.liveCalls
      ? '<button type="button" class="to-live" data-live title="the tool calls of the turn under way">under way</button>' : ""
    panel.innerHTML = `
      <div class="log-head">
        <span class="which" title="${esc(shownFor === LIVE ? window.liveCalls.prompt || "" : shownFor ? shownFor.querySelector(".hl, .date").textContent : "")}">${label(shownFor)}</span>
        <span class="tally">${Object.entries(tally).map(([k, n]) => `<span title="${n} ${NAMES[k]}">${icon(k)}${n}</span>`).join("")}${span ? `<span title="from the first step to the last">${span}</span>` : ""}</span>
        ${steps.some((s) => s.kind !== "thinking") ? '<button type="button" class="all" data-all aria-keyshortcuts="O">open all</button>' : ""}
        ${jump}<button type="button" data-close title="close (Esc)" aria-label="close the tool calls">×</button>
      </div>
      <div class="log-steps">${steps.length ? steps.map(step).join("") : `<p class="log-empty">${empty}</p>`}</div>`
    const box = panel.querySelector(".log-steps")
    if (kept) {
      kept.open.forEach((n) => flip(box.querySelector(`.step[data-n="${n}"]`)))
      box.scrollTop = kept.end ? box.scrollHeight : kept.top
    } else {
      at = -1
      if (shownFor === LIVE) box.scrollTop = box.scrollHeight
    }
    nameAll()
    point(at, false)
  }

  // a step opened shows what it asked for and what came back; a thought, its whole text
  function flip(el, open = !el.classList.contains("open")) {
    if (!el || el.classList.contains("open") === open) return
    el.classList.toggle("open", open)
    const s = shownSteps[+el.dataset.n]
    if (s.kind === "thinking") return
    if (!open) return el.querySelector(".detail")?.remove()
    el.insertAdjacentHTML("beforeend", `<div class="detail">${detail(s, +el.dataset.n)}</div>`)
  }
  const stepEls = () => [...panel.querySelectorAll(".log-steps .step")]
  const allOpen = () => stepEls().length > 0 && stepEls().every((el) => el.classList.contains("open"))
  const nameAll = () => { const all = panel.querySelector("[data-all]"); if (all) all.textContent = `${allOpen() ? "close" : "open"} all` }
  function flipAll() {
    const open = !allOpen()
    stepEls().forEach((el) => flip(el, open))
    nameAll()
    point(at)
  }

  // ---- the keys, while the log holds them: `at` is the step they are on, -1 none yet

  let keyed = false, at = -1
  function point(n, scroll = true) {
    const els = stepEls()
    at = els.length ? Math.max(-1, Math.min(n, els.length - 1)) : -1
    els.forEach((el, k) => el.classList.toggle("cur", keyed && k === at))
    if (scroll && els[at]) els[at].scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" })
  }
  function steer(on) {
    keyed = on
    panel.classList.toggle("keyed", on)
    if (on && at < 0) at = shownFor === LIVE ? stepEls().length - 1 : 0
    point(at)
  }

  panel.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) return toggle(false)
    if (e.target.closest("[data-all]")) return flipAll()
    if (e.target.closest("[data-live]")) { toLive = true; return draw() }
    const more = e.target.closest(".more")
    if (more) {
      const pre = more.previousElementSibling, [n, k] = pre.dataset.whole.split(".").map(Number)
      const [, code, lang] = pieces(shownSteps[n])[k]
      pre.querySelector("code").innerHTML = lit(code, lang)
      return more.remove()
    }
    const head = e.target.closest(".step > button")
    if (!head) return
    const el = head.parentElement
    flip(el)
    nameAll()
    at = stepEls().indexOf(el)
    steer(true)
  })
  // a click anywhere else hands the keys back to the turns
  document.addEventListener("mousedown", (e) => { if (keyed && !panel.contains(e.target)) steer(false) })

  // while open, the turn under way's calls are loaded again every POLL; the log is drawn again where
  // they changed, and its running calls' times move on where they did not
  let polling = null, liveWas = null
  const poll = async () => {
    await loadLive()
    const live = JSON.stringify(window.liveCalls ?? null)
    if (live !== liveWas || target() !== shownFor) draw()
    else panel.querySelectorAll(".took.running").forEach((el) => (el.textContent = `${took(secs(el.dataset.at, new Date().toISOString()))}…`))
    liveWas = live
  }

  const isOpen = () => panel.classList.contains("open")
  async function toggle(open = !isOpen()) {
    toggleButton.setAttribute("aria-expanded", String(open))
    clearInterval(polling)
    if (!open) { steer(false); return panel.classList.remove("open") }
    if (!window.toolCalls) { panel.innerHTML = '<p class="log-empty">loading the tool calls…</p>'; panel.classList.add("open"); await load() }
    if (toggleButton.getAttribute("aria-expanded") !== "true") return  // closed while it loaded
    liveWas = JSON.stringify(window.liveCalls ?? null)
    draw()
    panel.classList.add("open")
    // opened again, it shows what it last had at once, and the turn under way as of now a moment later
    poll()
    polling = setInterval(poll, POLL)
  }
  toggleButton.addEventListener("click", () => toggle())
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
    if (e.key === "l") { toggle(); e.preventDefault() }
    else if (e.key === "Escape" && isOpen()) toggle(false)
  })
  // ahead of page.js's keys, in the capture phase, so the log's j and k never also move the turns
  let gArmed = 0
  addEventListener("keydown", (e) => {
    if (!isOpen() || e.ctrlKey || e.metaKey || e.altKey || typing(e)) return
    if (e.key === "Tab" && !e.shiftKey) steer(!keyed)
    else if (!keyed) return
    else if (e.key === "j") point(at + 1)
    else if (e.key === "k") point(Math.max(0, at - 1))
    else if (e.key === "G") point(stepEls().length - 1)
    else if (e.key === "g") { if (Date.now() - gArmed < 500) { point(0); gArmed = 0 } else gArmed = Date.now() }
    else if (e.key === "o" || e.key === "Enter") { flip(stepEls()[at]); nameAll(); point(at) }
    else if (e.key === "O") flipAll()
    else return
    e.preventDefault()
    e.stopImmediatePropagation()
  }, true)
  // whatever moves the page's focus (j, k, a click, n, t) moves the open log with it, off the turn under way
  new MutationObserver(() => {
    if (cursor() !== cursorWas) { cursorWas = cursor(); toLive = false }
    if (isOpen() && window.toolCalls && target() !== shownFor) draw()
  })
    .observe(pane, { subtree: true, attributes: true, attributeFilter: ["class"] })
})()
