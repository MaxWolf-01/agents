// The stepping: each chapter's picture grows to the step being read.
//
// A step is being read once its top has crossed the reading line (half way
// down the window; lower on a narrow one, where the picture sits above the
// text). One step at a time is in focus: the last one past the line, whose
// text is in the accent; the steps before it are marked past. For a chapter
// with k of its steps past that line:
// - a figure shows every element whose data-step is at most k, those of step k
//   in the accent, and its camera closes in on what is drawn so far while that
//   still reads; before its first step it shows step 1 without the accent;
// - a screenshot closes in on step k's region and dims the rest; before its
//   first step, and for a step with no region, it is shown whole.
// With "whole" on the root (head.js) the page is a plain article (story.css):
// every picture complete at its own size, nothing in focus, and the keys
// scroll as on any page. Switching keeps the chapter being read in view.
// Stepped, the arrow keys, j and k, and Space move one step, scrolling the
// page to it; Home and End go to the top and to the last step.

(() => {
  const root = document.documentElement
  const reduce = matchMedia("(prefers-reduced-motion: reduce)")
  const narrow = matchMedia("(max-width: 60rem)")
  const whole = () => root.classList.contains("whole")
  const READ = 0.7 // smallest scale, SVG units to CSS pixels, a growing figure is drawn at
  const MAX_FIGURE = 1.25 // largest scale a figure is drawn at
  const MAX_SHOT = 0.8 // largest scale, image pixels to CSS pixels, of a 2x screenshot
  const PAD = 24 // SVG units kept around what a figure's camera frames
  const GRAPHIC = "path, line, polyline, polygon, rect, circle, ellipse, text, image, use"
  const MARKERS = [["markerStart", "marker-start"], ["markerMid", "marker-mid"], ["markerEnd", "marker-end"]]

  const steps = [...document.querySelectorAll(".beat")]
  const chapters = [...document.querySelectorAll(".chapter")].map(setup)

  function setup(el) {
    const ch = { el, steps: [...el.querySelectorAll(".beat")], stage: el.querySelector(".stage"), shown: "" }
    if (!ch.stage) return ch
    ch.kind = ch.stage.dataset.kind
    ch.frame = ch.stage.querySelector(".frame")
    ch.canvas = ch.stage.querySelector(".canvas")
    ch.W = +ch.canvas.dataset.w
    ch.H = +ch.canvas.dataset.h
    if (ch.kind === "screenshot") {
      ch.focus = ch.canvas.querySelector(".focus")
      ch.regions = ch.steps.map((s) => (s.dataset.region ? s.dataset.region.split(" ").map(Number) : null))
    } else {
      ch.svg = ch.canvas.querySelector("svg")
      ch.stepped = ch.stage.hasAttribute("data-stepped")
      ch.marked = [...ch.svg.querySelectorAll("[data-step]")]
    }
    return ch
  }

  // What each drawn element of a figure covers, in SVG units, and how it takes
  // the accent: a text by its fill, a line by its stroke, a box by a wash, a
  // small solid shape by its fill. A shape or a text filled with the ground is a
  // mask or a number knocked out of a disc, and one filled with the accent
  // already says "you"; both keep their fill.
  // Measured once, with the canvas unscaled.
  function measure(ch) {
    ch.canvas.style.transform = "none"
    const base = ch.svg.getBoundingClientRect()
    const unit = base.width / ch.W
    const ground = getComputedStyle(document.body).backgroundColor
    const probe = document.createElement("span")
    probe.style.color = "var(--accent)"
    document.body.append(probe)
    const accent = getComputedStyle(probe).color
    probe.remove()
    ch.boxes = []
    ch.markerUsers = []
    const accentMarkers = new Set()
    for (const g of ch.svg.querySelectorAll(GRAPHIC)) {
      if (g.closest("defs, marker, clipPath, mask, pattern, symbol")) continue
      const host = g.closest("[data-step]")
      const r = g.getBoundingClientRect()
      const w = r.width / unit, h = r.height / unit
      if (w || h) ch.boxes.push({ step: host ? +host.dataset.step : 0, x: (r.left - base.left) / unit, y: (r.top - base.top) / unit, w, h })
      if (!host) continue
      const cs = getComputedStyle(g)
      const roles = []
      if (g.tagName === "text") {
        // a number knocked out of a disc is drawn in the ground, and stays so
        if (cs.fill !== ground && cs.fill !== accent) roles.push("text")
      } else {
        const stroked = cs.stroke !== "none" && parseFloat(cs.strokeWidth) > 0
        const filled = cs.fill !== "none" && cs.fillOpacity !== "0" && !/,\s*0\)$/.test(cs.fill) &&
          cs.fill !== ground && cs.fill !== accent
        if (stroked) roles.push("stroke")
        if (filled) roles.push(stroked || w * h > 900 ? "fill" : "solid")
      }
      if (roles.length) g.dataset.hl = roles.join(" ")
      const used = []
      for (const [prop, css] of MARKERS) {
        const id = /url\(["']?#([^"')]+)/.exec(cs.getPropertyValue(css))?.[1]
        if (id) { used.push([prop, id]); accentMarkers.add(id) }
      }
      if (used.length) ch.markerUsers.push([g, used])
    }
    // an accent copy of each marker a stepped line uses, so its arrowhead turns with it
    for (const id of accentMarkers) {
      const marker = ch.svg.querySelector(`marker[id="${CSS.escape(id)}"]`)
      if (!marker || ch.svg.querySelector(`marker[id="${CSS.escape(id)}-hl"]`)) continue
      const copy = marker.cloneNode(true)
      copy.id = `${id}-hl`
      const originals = [...marker.querySelectorAll("*")]
      ;[...copy.querySelectorAll("*")].forEach((part, i) => {
        const cs = getComputedStyle(originals[i])
        part.removeAttribute("class")
        part.style.fill = cs.fill === "none" ? "none" : "var(--accent)"
        part.style.stroke = cs.stroke === "none" ? "none" : "var(--accent)"
      })
      marker.after(copy)
    }
  }

  function union(boxes) {
    if (!boxes.length) return null
    const x = Math.min(...boxes.map((b) => b.x)), y = Math.min(...boxes.map((b) => b.y))
    const r = Math.max(...boxes.map((b) => b.x + b.w)), btm = Math.max(...boxes.map((b) => b.y + b.h))
    return { x, y, w: r - x, h: btm - y }
  }

  // The translate that puts point (cx, cy) of a W x H canvas at the frame's
  // centre at scale s, kept so the canvas never pulls away from an edge it covers.
  function aim(ch, s, cx, cy) {
    const place = (size, frame, c) =>
      size * s <= frame ? (frame - size * s) / 2 : Math.min(0, Math.max(frame - size * s, frame / 2 - c * s))
    return { s, tx: place(ch.W, ch.fw, cx), ty: place(ch.H, ch.fh, cy) }
  }

  const fitScale = (ch, w, h) => Math.min(ch.fw / w, ch.fh / h)

  function figureView(ch, k) {
    const all = fitScale(ch, ch.W, ch.H)
    if (!ch.stepped || !ch.boxes) return aim(ch, Math.min(all, MAX_FIGURE), ch.W / 2, ch.H / 2)
    const drawn = union(ch.boxes.filter((b) => b.step <= k))
    if (!drawn) return aim(ch, Math.min(all, MAX_FIGURE), ch.W / 2, ch.H / 2)
    const pad = { x: drawn.x - PAD, y: drawn.y - PAD, w: drawn.w + 2 * PAD, h: drawn.h + 2 * PAD }
    const s = Math.max(all, Math.min(fitScale(ch, pad.w, pad.h), MAX_FIGURE))
    // Drawn so far too tall to read whole: zoom in as far as READ, but never past
    // the figure's full width, and follow what this step added, from its top
    // where that is taller than the frame.
    const follow = Math.max(s, Math.min(READ, ch.fw / ch.W))
    if (follow <= s + 1e-6) return aim(ch, s, pad.x + pad.w / 2, pad.y + pad.h / 2)
    const fresh = union(ch.boxes.filter((b) => b.step === k)) || pad
    const span = (start, size, frame) => start + Math.min(size, frame / follow - 2 * PAD) / 2
    return aim(ch, follow, span(fresh.x, fresh.w, ch.fw), span(fresh.y, fresh.h, ch.fh))
  }

  function shotView(ch, region) {
    const all = fitScale(ch, ch.W, ch.H)
    if (!region) return aim(ch, all, ch.W / 2, ch.H / 2)
    const [x, y, w, h] = region
    const rw = w * ch.W, rh = h * ch.H
    const s = Math.max(all, Math.min(fitScale(ch, rw * 1.12, rh * 1.12), MAX_SHOT))
    return aim(ch, s, (x + w / 2) * ch.W, (y + h / 2) * ch.H)
  }

  // The frame a stepped picture is fitted into; a whole one sizes itself.
  function layout(ch) {
    if (whole()) return
    const cs = getComputedStyle(ch.stage)
    const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)
    const padY = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
    ch.fw = ch.stage.getBoundingClientRect().width - padX
    ch.fh = ch.stage.getBoundingClientRect().height - padY
  }

  function render(ch, k, active, passed) {
    let view
    if (ch.kind === "screenshot") {
      const region = whole() || passed === 0 ? null : ch.regions[k - 1]
      view = whole() ? null : shotView(ch, region)
      ch.focus.classList.toggle("on", !!region)
      if (region) {
        const [x, y, w, h] = region
        Object.assign(ch.focus.style, { left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` })
      }
    } else {
      for (const m of ch.marked) {
        const n = +m.dataset.step
        m.classList.toggle("is-later", n > k)
        m.classList.toggle("is-new", active && n === k)
      }
      for (const [g, used] of ch.markerUsers || []) {
        const hot = active && g.closest(".is-new")
        for (const [prop, id] of used) g.style[prop] = hot ? `url(#${id}-hl)` : ""
      }
      view = whole() ? null : figureView(ch, k)
    }
    if (whole()) {
      ch.canvas.style.transform = ""
      ch.canvas.style.removeProperty("--s")
    } else {
      ch.canvas.style.transform = `translate(${view.tx}px, ${view.ty}px) scale(${view.s})`
      ch.canvas.style.setProperty("--s", view.s)
    }
    ch.el.dataset.shown = whole() ? "whole" : String(k)
    ch.el.dataset.accent = active && (ch.kind === "screenshot" ? !!ch.regions[k - 1] : !!ch.stepped) ? String(k) : ""
  }

  const readingLine = () => innerHeight * (narrow.matches ? 0.72 : 0.5)

  function currentIndex() {
    const y = readingLine()
    let current = -1
    steps.forEach((s, i) => { if (s.getBoundingClientRect().top <= y + 1) current = i })
    return current
  }

  function update(force) {
    const y = readingLine()
    const current = whole() ? -1 : currentIndex()
    steps.forEach((s, i) => {
      s.classList.toggle("is-current", i === current)
      s.classList.toggle("is-past", i < current)
    })
    for (const ch of chapters) {
      if (!ch.stage) continue
      const passed = ch.steps.filter((s) => s.getBoundingClientRect().top <= y + 1).length
      const k = whole() ? ch.steps.length : Math.max(1, passed)
      const active = !whole() && passed >= 1
      const key = `${k} ${active} ${passed} ${whole()}`
      if (!force && key === ch.shown) continue
      ch.shown = key
      render(ch, k, active, passed)
    }
  }

  let frame = 0
  const schedule = () => { if (!frame) frame = requestAnimationFrame(() => { frame = 0; update(false) }) }

  // ---- the keys ----
  let pending = null
  let pendingTimer = 0
  function go(i) {
    i = Math.max(-1, Math.min(steps.length - 1, i))
    pending = i
    clearTimeout(pendingTimer)
    pendingTimer = setTimeout(() => { pending = null }, 1500)
    const top = i < 0 ? 0 : scrollY + steps[i].getBoundingClientRect().top - (readingLine() - innerHeight * 0.12)
    scrollTo({ top, behavior: reduce.matches ? "auto" : "smooth" })
  }
  addEventListener("scrollend", () => { pending = null })

  addEventListener("keydown", (e) => {
    if (whole() || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return
    const t = e.target
    if (t.closest && t.closest("input, textarea, select, [contenteditable]")) return
    const onControl = t.closest && t.closest("button, a, summary")
    const from = pending ?? currentIndex()
    let to
    switch (e.key) {
      case "ArrowDown": case "ArrowRight": case "j": to = from + 1; break
      case "ArrowUp": case "ArrowLeft": case "k": to = from - 1; break
      case " ": if (onControl) return; to = e.shiftKey ? from - 1 : from + 1; break
      case "Home": to = -1; break
      case "End": to = steps.length - 1; break
      default: return
    }
    e.preventDefault()
    go(to)
  })

  // ---- start ----
  function relayout() {
    for (const ch of chapters) if (ch.stage) layout(ch)
    update(true)
  }

  // The chapter being read: the last whose top is above the reading line.
  let reading = null
  const track = () => {
    const y = readingLine()
    reading = null
    for (const ch of chapters) if (ch.el.getBoundingClientRect().top <= y) reading = ch
  }

  // Switching between stepped and whole moves every chapter; bring the one
  // being read back to the top of the window, from its heading.
  function switched() {
    const ch = reading
    relayout()
    if (!ch) return
    const heading = ch.el.querySelector("h2")
    scrollTo({ top: scrollY + heading.getBoundingClientRect().top - parseFloat(getComputedStyle(root).scrollPaddingTop || 0), behavior: "auto" })
    track()
  }

  for (const ch of chapters) if (ch.stage) layout(ch)
  update(true)
  track()
  addEventListener("scroll", schedule, { passive: true })
  addEventListener("scroll", track, { passive: true })
  document.addEventListener("story:whole", switched)
  const resized = new ResizeObserver(relayout)
  for (const ch of chapters) if (ch.stage) resized.observe(ch.stage)

  const settle = () => {
    for (const ch of chapters) if (ch.svg && ch.stepped) measure(ch)
    relayout()
    requestAnimationFrame(() => requestAnimationFrame(() => {
      for (const ch of chapters) if (ch.canvas) ch.canvas.classList.add("ready")
      root.dataset.story = "ready"
    }))
  }
  document.fonts.ready.then(settle, settle)
})()
