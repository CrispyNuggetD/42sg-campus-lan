# Proposed milestone: a Textual frontend

[← Experimental roadmap](roadmap.md) · [Documentation contents](README.md)

**Status: planned exploration, not implemented or scheduled.** Textual is a
candidate framework, not a new runtime dependency in this release. This proposal
is separate from the Life OS/LLM experiment. A polished campus community app
should still clearly identify itself as student-built and unofficial.

## Direction

Build a new presentation layer with [Textual](https://textual.textualize.io/),
reusing LAN42’s networking, authentication, access policy, caches and file-sharing
services. Extract UI-independent state and actions from the current client as
needed. Do not embed curses drawing/input inside Textual’s event loop or rewrite
the backend merely to change the interface. Keep the current launcher/client
available during evaluation; preserve consent and security boundaries throughout.

Start with Textual’s built-in `textual-dark` as a prototype baseline. Compare
`nord` with the same screens before choosing a default. Then register a small
LAN42 theme using semantic variables rather than hard-coded widget colours.
Textual CSS is its own styling system, not browser CSS or an HTML renderer.

## Initial branding and interaction brief

This is a starting specification to validate, not a finished visual identity.
Use the README, command guide and `website/page.css` as the existing references.

| Element | Proposed rule |
| --- | --- |
| Identity | LAN42 BETA; “Good company. A few good commands.”; Christopher Nah / hnah; student-built, unofficial. |
| Palette | Navy `#13293c`, mint `#a8e6cf`, blue `#2853b5`; web light background `#eef3f7`. Adapt semantic colours for readable terminal light/dark themes. |
| Typography | Terminal-provided monospace; restrained bold and hierarchy, consistent spacing, no dependency on decorative glyphs. |
| Layout | Stable header with host availability, sign-in and quiet state; task navigation; main content; discoverable command/action footer. |
| Navigation | Keyboard-complete workflows, visible focus, mouse support, command palette; preserve slash-command access where appropriate. |
| States | Explicit loading, empty, guest, host-offline, stale-data, denied, error and reconnect states; useful recovery actions. |
| Consent | Clearly separate join/upload, incoming files, notifications and sound. Defaults and existing opt-outs remain meaningful. |
| Accessibility | Do not encode status only by colour; support narrow terminals, resizing, readable contrast and reduced visual noise. Validate terminal/assistive-tool limitations rather than promising universal accessibility. |
| Privacy | No credentials or personal details in screenshots, fixtures, debug panels or design demos. |

The goal is a coherent product experience, not a screen crowded with every
feature. A new guest should understand what works now, what needs sign-in and
what depends on the campus host without knowing command names in advance.

## Learning and delivery stages

1. **Understand:** map the current guest, sign-in and file-sharing journeys;
   identify friction with a few willing peers. Write down the reasoning behind
   layout, hierarchy and interaction decisions.
2. **Prototype:** build a separate, fake-data Textual demonstration of the home,
   cluster view and preferences screens. Compare themes, keyboard navigation and
   offline/error states before connecting any live services.
3. **Separate:** introduce explicit UI state/actions and service adapters. Keep
   blocking network/file work off the UI loop; preserve authentication and
   consent checks at their existing service boundaries.
4. **Integrate:** connect one complete user journey, then migrate other screens
   incrementally. Existing games may keep their current interfaces initially.
5. **Validate:** use Textual’s headless Pilot tests for keys, clicks and resizing,
   plus carefully reviewed visual snapshots and real Mac/campus-terminal checks.
   Check guest/host-loss flows, reconnect, consent, exam quiet and responsiveness.
6. **Graduate:** document supported terminals/Python versions, dependency and
   installation costs, migration/rollback and known gaps before making it default.

Christopher’s learning objective is frontend engineering: information
architecture, component/state design, styling, interaction and usability testing.
AI can teach, scaffold and review; maintain short design decisions and hands-on
exercises so the owner can explain and modify the resulting UI. Quality should
be demonstrated through decisions, behaviour and evaluation, not inferred from
whether code was typed manually or generated.

## Version decision

**V3 beta is the working product-milestone candidate; V4 is possible if another
major milestone lands first.** No number is reserved and this documentation does
not change the server version. Visual ambition alone does not require a semantic
major increment. At graduation, document actual compatibility changes (commands,
configuration, runtime requirements, client/protocol support) and choose the
release category under [the versioning policy](versioning.md). Keep wire protocol
versioning separate from the UI/product milestone.

## Primary references

- [Textual themes and custom theme variables](https://textual.textualize.io/guide/design/)
- [Textual CSS](https://textual.textualize.io/guide/CSS/)
- [Workers](https://textual.textualize.io/guide/workers/)
- [Headless interaction and snapshot testing](https://textual.textualize.io/guide/testing/)

## Appendix: architecture considerations and future learning

### Immediate scope: start small with Textual

Christopher’s chosen starting point is a modest Textual prototype, not a
framework competition or a general-purpose frontend platform. Learn one complete
journey first: open LAN42, understand host availability, sign in and view a
cluster snapshot. Use fake data initially, include loading/offline/denied states,
and get feedback before expanding. The current client remains available during
evaluation; choosing Textual for this first step does not commit every future
interface to it.

The learning goal includes interaction design: understandable navigation,
keyboard and mouse use, visible focus, meaningful button states, feedback,
error recovery and restrained transitions. Professional quality should follow
from clear behaviour and evaluation, not from a framework name or visual theme.

### Possible later boundary: one service, several frontends

LAN42 already mediates selected 42 API reads with access policy and caching.
A future evolution could formalize a LAN42 application contract consumed by
curses, Textual or a browser frontend. This is an architectural consideration,
not a commitment to ship a public API or support arbitrary third-party clients.

Candidate operations include capability/host status, sign-in/out, cached cluster
snapshots with freshness, messaging, flock discovery/join and appropriately
scoped preferences. Extract only the operations needed by an actual journey;
avoid designing a broad abstraction before a second consumer demonstrates its
value. Version compatibility and deprecation would need an explicit policy if
independent frontends become supported.

Expose **LAN42 operations**, not an unrestricted proxy accepting arbitrary 42
API paths. The service remains responsible for identity, Singapore scope,
authorization, cache sharing and rate limits. Frontends do not receive the
host’s upstream credentials or gain privileges by supplying a role field.
Keep local file selection, browser opening, notifications and audio under the
client’s own consent and capabilities. A browser and terminal may offer
different features; capability discovery should explain those differences.

### Other tools exist; learning can come later

| Option | Future learning relevance | Current decision |
| --- | --- | --- |
| Textual / Python | Stateful terminal interfaces, widgets, layouts, events, styling and UI tests. | Start here with a small prototype. |
| Bubble Tea / Go | An alternative TUI architecture and an opportunity to learn Go and its application ecosystem. | Awareness and possible later exploration; no Go rewrite planned. |
| prompt_toolkit / Python | Command-entry and full-screen terminal interaction design. | An alternative to understand, not an additional dependency now. |
| Browser UI, potentially React | Web components, browser interaction, responsive layout and accessibility. | A possible later learning project, not part of the initial Textual scope. |

These tools occupy different roles. Flask is a Python web framework, Node.js a
JavaScript runtime, React a UI library and Bootstrap a frontend toolkit; they
are not interchangeable choices on one list. HTML and CSS remain useful
foundations. Knowing that these ecosystems exist in professional development
helps guide future learning; adopting all of them would not make LAN42 more
professional by itself. There is no universal “TUI gold standard” selected here.

Further primary references:
[Bubble Tea](https://github.com/charmbracelet/bubbletea),
[prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/en/master/),
[React](https://react.dev/learn), [Flask](https://flask.palletsprojects.com/),
[Node.js](https://nodejs.org/en/about),
[Bootstrap](https://getbootstrap.com/docs/5.3/getting-started/introduction/).

### Interaction request: adaptive pointer feedback

Explore iPadOS-inspired **adaptive pointer / pointer morphing** with a magnetic
highlight around buttons and navigation targets. The goal is to make available
actions feel tangible, rather than relying only on a hand-shaped cursor.
Apple describes pointer shape changes, highlight/lift effects and magnetism in
its [pointer design guidance](https://developer.apple.com/videos/play/wwdc2020/10640/).

The website now provides an iPadOS-inspired adaptive pointer as a progressive
enhancement, not native iPadOS integration. It is on by default for eligible
mouse/trackpad users, with a persistent bottom-right pointer dock. All links, buttons and disclosure controls share a rounded highlight. A single
borderless translucent shape continuously interpolates position and size; it
forms an I-beam over text and text fields without altering native selection or
editing. The overlay never changes actual click targets. See the
[website design milestone](website-changelog.md). Touch, reduced-motion and forced-colour preferences use the native
pointer. This is website polish, not a completed Textual migration.
Respect reduced-motion preferences, keyboard focus, touch input, browser zoom
and high-contrast needs. No tracking, artificial click delays or moving targets.

Textual remains the initial frontend scope. Terminal mouse events do not give
LAN42 control over the operating system pointer shape; use widget hover/focus
feedback there. Assess custom browser pointer effects separately from the TUI.
