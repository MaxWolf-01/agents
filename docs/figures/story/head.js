// Loaded in the head, so the page's two preferences are on the root before the
// first paint.
// - The scheme: ?theme=day|night pins it, the toggle flips it, and otherwise
//   the page follows the system, also when the system changes while it is open.
//   data-theme on the root is the whole switch.
// - Whole figures: the page read as a plain article, each chapter's intro, its
//   picture complete, then its steps as paragraphs, instead of pictures
//   growing step by step.
//   ?final turns it on for this load (?final=0 off); the switch turns it on or
//   off and is remembered in localStorage. The class "whole" on the root is
//   the whole switch; story.css and story.js read it.
// The class "js" says the stepping script will run, so the stylesheet lays the
// chapters out for it.

(() => {
  const root = document.documentElement
  const params = new URLSearchParams(location.search)
  const KEY = "mx-story-whole"
  root.classList.add("js")

  const asked = params.get("theme")
  const system = matchMedia("(prefers-color-scheme: dark)")
  let chosen = asked === "day" || asked === "night"
  const setTheme = (night) => {
    root.dataset.theme = night ? "night" : "day"
    const button = document.getElementById("scheme")
    if (button) button.setAttribute("aria-label", night ? "switch to day" : "switch to night")
  }
  setTheme(chosen ? asked === "night" : system.matches)
  system.addEventListener("change", (e) => chosen || setTheme(e.matches))

  const stored = () => {
    try { return localStorage.getItem(KEY) === "1" } catch { return false }
  }
  const showWhole = () => {
    const button = document.getElementById("whole")
    if (button) button.setAttribute("aria-checked", String(root.classList.contains("whole")))
  }
  const setWhole = (on) => {
    root.classList.toggle("whole", on)
    showWhole()
    document.dispatchEvent(new CustomEvent("story:whole"))
  }
  setWhole(params.has("final") ? params.get("final") !== "0" : stored())

  document.addEventListener("DOMContentLoaded", () => {
    setTheme(root.dataset.theme === "night")
    showWhole()
    document.getElementById("scheme").addEventListener("click", () => {
      chosen = true
      setTheme(root.dataset.theme !== "night")
    })
    document.getElementById("whole").addEventListener("click", () => {
      const on = !root.classList.contains("whole")
      try { localStorage.setItem(KEY, on ? "1" : "0") } catch {}
      setWhole(on)
    })
  })
})()
