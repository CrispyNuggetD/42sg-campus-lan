# Website design history

[← Home](../README.md) · [User guide](README.md) · [Frontend plan](frontend-milestone.md)

Website milestones record meaningful changes to the public experience. They do
not increment the LAN42 server version or announce an implemented TUI feature.
The [server changelog](../CHANGELOG.md) remains separate.

## 27 October 2026 · Adaptive interaction design milestone

- Established the navy/mint branded website shell, Markdown-generated task guides
  and roadmap, and a one-minute student home page with contributor credits.
- Refined home into a compact introduction, asymmetric install/access layout,
  copyable command strip, lightweight sharing/quiet section and contributor
  closing area. Layout and content work without JavaScript; optional copy and
  pointer controls progressively enhance supported browsers. The install copy
  action sits in the terminal toolbar with a clear label, copy icon and strong
  contrast.
- Made the creator identity visible near the introduction, linking Christopher
  Nah’s GitHub and hnah’s Intra profile. The closing section distinguishes
  creator/maintainer from Darren’s alpha-testing credit.
- Command search now presents matches directly below the input with a visible
  count, empty state and Clear/Escape reset.
- Introduced default-on adaptive pointer feedback for supported desktop devices,
  with a persistent browser-local off switch and native touch/reduced-motion/
  high-contrast fallbacks.
- Refined the effect into one continuous, borderless translucent shape: position,
  size, corners and text-beam details interpolate together. Links remain semantic
  links and share the target highlight; text fields and selectable text receive
  a smoothly formed I-beam without changing actual editing or selection.

This is a concrete website design direction to evaluate, not a claim of native
iPadOS integration. Layout, focus and interaction lessons can inform the planned
Textual frontend; the terminal cannot reproduce OS pointer-shape control.
