// The viewer: a click on a picture opens it over the page, fitted to the
// window. Drag pans; the wheel, a pinch, and the + and - keys zoom; 0 fits it
// again; a double click toggles between fitted and full size; Esc, the close
// button, or a click on the backdrop closes it. The picture follows the page's
// scheme while it is open.
//
// Each picture on the page is a button.open carrying data-day and data-night
// (the two renders, equal where there is one), data-title and data-text (its
// section's heading and lines). The page holds one #viewer, laid out in
// index.html.

(() => {
  const viewer = document.getElementById("viewer")
  const stage = viewer.querySelector(".stage")
  const img = stage.querySelector("img")
  const title = viewer.querySelector(".caption .v-h3")
  const text = viewer.querySelector(".caption .v-small")
  const zoomLabel = viewer.querySelector(".zoom")
  const root = document.documentElement

  const MAX = 2 // CSS pixels per image pixel: each pixel of a 2x render drawn two wide, 4x its size on the page
  const PAD = 16
  let trigger = null // the button that opened the viewer, focused again on close
  let s = 1 // scale
  let x = 0 // image offset in the stage, CSS pixels
  let y = 0
  let fitted = true

  const night = () => root.dataset.theme === "night"
  const sourceFor = (button) => (night() ? button.dataset.night : button.dataset.day)

  const box = () => stage.getBoundingClientRect()
  const fitScale = () => {
    const { width, height } = box()
    const w = img.naturalWidth || 1
    const h = img.naturalHeight || 1
    return Math.min((width - 2 * PAD) / w, (height - 2 * PAD) / h, MAX)
  }

  // Keep the picture in view: centred along an axis it does not fill, and
  // never dragged past its own edge along one it does.
  const clamp = () => {
    const { width, height } = box()
    const w = img.naturalWidth * s
    const h = img.naturalHeight * s
    x = w <= width - 2 * PAD ? (width - w) / 2 : Math.min(PAD, Math.max(width - w - PAD, x))
    y = h <= height - 2 * PAD ? (height - h) / 2 : Math.min(PAD, Math.max(height - h - PAD, y))
  }

  const paint = () => {
    clamp()
    img.style.transform = `translate(${x}px, ${y}px) scale(${s})`
    zoomLabel.textContent = `${Math.round((s / fitScale()) * 100)}%`
  }

  const fit = () => {
    s = fitScale()
    fitted = true
    paint()
  }

  // Zoom by a factor around a point of the stage, which stays put on screen.
  const zoomAt = (px, py, factor) => {
    const next = Math.min(MAX, Math.max(fitScale(), s * factor))
    x = px - (px - x) * (next / s)
    y = py - (py - y) * (next / s)
    s = next
    fitted = s === fitScale()
    paint()
  }

  const centre = () => {
    const { width, height } = box()
    return [width / 2, height / 2]
  }

  const focusable = () => [...viewer.querySelectorAll("button")]

  const open = (button) => {
    trigger = button
    title.textContent = button.dataset.title
    text.textContent = button.dataset.text
    img.alt = button.querySelector("img:not([hidden])")?.alt || button.dataset.title
    viewer.hidden = false
    root.classList.add("viewing")
    img.onload = fit
    img.src = sourceFor(button)
    if (img.complete && img.naturalWidth) fit()
    viewer.querySelector(".close").focus()
  }

  const close = () => {
    viewer.hidden = true
    root.classList.remove("viewing")
    img.removeAttribute("src")
    trigger?.focus()
    trigger = null
  }

  for (const button of document.querySelectorAll("button.open")) {
    button.addEventListener("click", () => open(button))
  }

  viewer.querySelector(".close").addEventListener("click", close)
  viewer.querySelector(".fit").addEventListener("click", fit)
  viewer.querySelector(".in").addEventListener("click", () => zoomAt(...centre(), 1.25))
  viewer.querySelector(".out").addEventListener("click", () => zoomAt(...centre(), 0.8))

  // The page's scheme moved while the viewer is open: show the other render
  // where there is one, keeping the zoom.
  new MutationObserver(() => {
    if (!trigger) return
    const src = sourceFor(trigger)
    if (img.getAttribute("src") === src) return
    img.onload = () => (fitted ? fit() : paint())
    img.src = src
  }).observe(root, { attributes: true, attributeFilter: ["data-theme"] })

  window.addEventListener("resize", () => {
    if (!trigger) return
    if (fitted) fit()
    else paint()
  })

  stage.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault()
      const r = box()
      const unit = e.deltaMode === 1 ? 16 : 1
      // A pinch on a trackpad arrives as a wheel event with ctrlKey held and
      // small deltas, so it takes a steeper curve.
      const factor = Math.exp(-e.deltaY * unit * (e.ctrlKey ? 0.01 : 0.0015))
      zoomAt(e.clientX - r.left, e.clientY - r.top, factor)
    },
    { passive: false },
  )

  // Pointers: one drags, two pinch. A press that never moves and lands off the
  // picture is a click on the backdrop, which closes the viewer.
  const pointers = new Map()
  let moved = 0
  let pinch = null

  const pinchState = () => {
    const [a, b] = [...pointers.values()]
    const r = box()
    return {
      d: Math.hypot(a.x - b.x, a.y - b.y),
      mx: (a.x + b.x) / 2 - r.left,
      my: (a.y + b.y) / 2 - r.top,
    }
  }

  stage.addEventListener("pointerdown", (e) => {
    stage.setPointerCapture(e.pointerId)
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (pointers.size === 1) moved = 0
    if (pointers.size === 2) pinch = pinchState()
    stage.classList.add("dragging")
  })

  stage.addEventListener("pointermove", (e) => {
    const last = pointers.get(e.pointerId)
    if (!last) return
    const dx = e.clientX - last.x
    const dy = e.clientY - last.y
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
    moved += Math.abs(dx) + Math.abs(dy)
    if (pointers.size === 2 && pinch) {
      const now = pinchState()
      x += now.mx - pinch.mx
      y += now.my - pinch.my
      zoomAt(now.mx, now.my, now.d / pinch.d)
      pinch = now
    } else if (pointers.size === 1) {
      x += dx
      y += dy
      fitted = false
      paint()
    }
  })

  const release = (e) => {
    if (!pointers.has(e.pointerId)) return
    pointers.delete(e.pointerId)
    if (pointers.size < 2) pinch = null
    if (pointers.size === 0) {
      stage.classList.remove("dragging")
      // The stage captures the pointer, so the event's target is always the
      // stage: whether the press was on the picture is read from where it was.
      const r = img.getBoundingClientRect()
      const onPicture = e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom
      if (e.type === "pointerup" && moved < 4 && !onPicture) close()
    }
  }
  stage.addEventListener("pointerup", release)
  stage.addEventListener("pointercancel", release)

  img.addEventListener("dblclick", (e) => {
    const r = box()
    if (fitted) zoomAt(e.clientX - r.left, e.clientY - r.top, 1 / s)
    else fit()
  })

  document.addEventListener("keydown", (e) => {
    if (viewer.hidden) return
    const step = 80
    const keys = {
      Escape: close,
      "+": () => zoomAt(...centre(), 1.25),
      "=": () => zoomAt(...centre(), 1.25),
      "-": () => zoomAt(...centre(), 0.8),
      _: () => zoomAt(...centre(), 0.8),
      0: fit,
      ArrowLeft: () => ((x += step), (fitted = false), paint()),
      ArrowRight: () => ((x -= step), (fitted = false), paint()),
      ArrowUp: () => ((y += step), (fitted = false), paint()),
      ArrowDown: () => ((y -= step), (fitted = false), paint()),
    }
    if (e.key === "Tab") {
      // Focus stays inside the viewer while it is open.
      const all = focusable()
      const i = all.indexOf(document.activeElement)
      const next = e.shiftKey ? (i <= 0 ? all.length - 1 : i - 1) : (i + 1) % all.length
      all[next].focus()
      e.preventDefault()
      return
    }
    if (e.ctrlKey || e.metaKey || e.altKey || !(e.key in keys)) return
    e.preventDefault()
    keys[e.key]()
  })
})()
