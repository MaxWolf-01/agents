// The tool-call log: a drawer on the right, over the timeline, showing what the focused turn did
// (page.js marks that turn's block .cur), else the newest turn's. `log l` in the bar or l opens and
// closes it, and Esc closes it. The steps live beside the page in tool-calls.js, which the first
// opening loads, with the highlighter; until then the page holds none of them.
(() => {
  const toggleButton = document.getElementById("log-toggle")
  const pane = document.getElementById("turns-pane")
  const blocks = [...pane.querySelectorAll("[data-block]")]
  const HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js"
  const HLJS_SRI = "sha384-RH2xi4eIQ/gjtbs9fUXM68sLSi99C7ZWBRX1vDrVv6GQXRibxXLbwO2NGZB74MbU"
  const CUT = 1500  // the characters of a request or a result a step shows until "show all"

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
  const load = () => (loading ||= Promise.allSettled([script(toggleButton.dataset.src), script(HLJS, HLJS_SRI)]))

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
  const focused = () => blocks.find((b) => b.classList.contains("cur")) || blocks[0]
  const label = (b) => {
    if (!b) return "no turn yet"
    const [name, about] = b.matches("details.turn") ? [`turn ${b.id.slice(1)}`, b.querySelector(".hl").textContent]
      : ["chat turn", b.querySelector(".date").textContent]
    return `${esc(name)} <span class="hl">· ${esc(about)}</span>`
  }
  let shownFor = null

  const step = (s, n) => s.kind === "thinking"
    ? `<div class="step thinking" data-n="${n}"><button type="button">${icon("thinking")}<span class="subject">${esc(s.output)}</span></button></div>`
    : `<div class="step" data-n="${n}"><button type="button">${icon(s.kind)}<span class="verb">${esc(s.verb)}</span><span class="subject">${esc(s.subject)}</span>` +
      `${s.failed ? '<span class="failed" title="failed">✕</span>' : ""}<span class="took">${took(secs(s.at, s.done))}</span></button></div>`

  function draw() {
    shownFor = focused()
    const steps = (window.toolCalls && shownFor && window.toolCalls[shownFor.id]) || []
    shownSteps = steps
    const tally = {}
    steps.forEach((s) => (tally[s.kind] = (tally[s.kind] || 0) + 1))
    const first = steps[0], last = steps[steps.length - 1]
    const span = first ? took(secs(first.at, last.done || last.at)) : ""
    const empty = !window.toolCalls ? "the tool calls are not beside this page: the next turn's render writes them"
      : "no tool calls for this turn"
    panel.innerHTML = `
      <div class="log-head">
        <span class="which" title="${esc(shownFor ? shownFor.querySelector(".hl, .date").textContent : "")}">${label(shownFor)}</span>
        <span class="tally">${Object.entries(tally).map(([k, n]) => `<span title="${n} ${NAMES[k]}">${icon(k)}${n}</span>`).join("")}${span ? `<span title="from the first step to the last">${span}</span>` : ""}</span>
        <button type="button" data-close title="close (Esc)" aria-label="close the tool calls">×</button>
      </div>
      <div class="log-steps">${steps.length ? steps.map(step).join("") : `<p class="log-empty">${empty}</p>`}</div>`
  }

  panel.addEventListener("click", (e) => {
    if (e.target.closest("[data-close]")) return toggle(false)
    const more = e.target.closest(".more")
    if (more) {
      const pre = more.previousElementSibling, [n, k] = pre.dataset.whole.split(".").map(Number)
      const [, code, lang] = pieces(shownSteps[n])[k]
      pre.querySelector("code").innerHTML = lit(code, lang)
      return more.remove()
    }
    const head = e.target.closest(".step > button")
    if (!head) return
    const el = head.parentElement, s = shownSteps[+el.dataset.n]
    el.classList.toggle("open")
    if (s.kind === "thinking") return
    const open = el.querySelector(".detail")
    if (open) return open.remove()
    el.insertAdjacentHTML("beforeend", `<div class="detail">${detail(s, +el.dataset.n)}</div>`)
  })

  const isOpen = () => panel.classList.contains("open")
  async function toggle(open = !isOpen()) {
    toggleButton.setAttribute("aria-expanded", String(open))
    document.body.classList.toggle("log-open", open)
    if (!open) return panel.classList.remove("open")
    if (!window.toolCalls) { panel.innerHTML = '<p class="log-empty">loading the tool calls…</p>'; panel.classList.add("open"); await load() }
    if (toggleButton.getAttribute("aria-expanded") !== "true") return  // closed while it loaded
    draw()
    panel.classList.add("open")
  }
  toggleButton.addEventListener("click", () => toggle())
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || (e.target.matches && e.target.matches("input, textarea, select, [contenteditable]"))) return
    if (e.key === "l") { toggle(); e.preventDefault() }
    else if (e.key === "Escape" && isOpen()) toggle(false)
  })
  // whatever moves the page's focus (j, k, a click, n, t) moves the open log with it
  new MutationObserver(() => { if (isOpen() && window.toolCalls && focused() !== shownFor) draw() })
    .observe(pane, { subtree: true, attributes: true, attributeFilter: ["class"] })
})()
