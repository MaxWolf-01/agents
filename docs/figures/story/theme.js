// The scheme: ?theme=day|night pins it, the toggle in the header flips it,
// and otherwise the page follows the system, also when the system changes
// while the page is open. data-theme on the root is the whole switch; the
// stylesheet and the viewer read it. Loaded in the head, so the attribute is
// set before the first paint.

(() => {
  const root = document.documentElement
  const asked = new URLSearchParams(location.search).get("theme")
  const system = matchMedia("(prefers-color-scheme: dark)")
  let chosen = asked === "day" || asked === "night"

  const set = (night) => {
    root.dataset.theme = night ? "night" : "day"
    const button = document.getElementById("scheme")
    if (button) button.setAttribute("aria-label", night ? "switch to day" : "switch to night")
  }

  set(chosen ? asked === "night" : system.matches)
  system.addEventListener("change", (e) => chosen || set(e.matches))

  document.addEventListener("DOMContentLoaded", () => {
    set(root.dataset.theme === "night")
    document.getElementById("scheme").addEventListener("click", () => {
      chosen = true
      set(root.dataset.theme !== "night")
    })
  })
})()
