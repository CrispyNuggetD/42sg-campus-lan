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
