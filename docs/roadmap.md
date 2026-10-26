# Roadmap and collaboration

[← Project introduction](../README.md) · [Documentation contents](README.md)

These are possible project expansions, not release commitments or available
features. Scope and feasibility may change; no delivery date is promised.

## At a glance

| Direction | Status | Ways to help |
| --- | --- | --- |
| [Textual frontend](frontend-milestone.md) | Next planned exploration; start with one small journey. | Interaction design, Python/Textual learning, keyboard/mouse testing and peer feedback. |
| [Stable hosting](#reliability-and-hosting) | Open problem; no always-on service promised. | Deployment ideas, availability and privacy/access review. |
| [File-sharing review UI](#file-sharing-review) | Future interface idea; version retention already exists. | Useful diff/review workflows and understandable consent. |
| [Life OS × LAN42](#possible-milestone-life-os-lan42) | Longer-term experiment; feasibility undecided. | Gamification, experiment design and measured energy/resource estimates. |
| [Shared service / other frontends](frontend-milestone.md#appendix-architecture-considerations-and-future-learning) | Architectural consideration and future learning. | Feedback after the first Textual journey works; no broad platform rewrite now. |

## Get involved

Interested in building, testing, designing or questioning an idea? Small,
specific contributions and thoughtful feedback are welcome. You do not need to
sign up for an entire milestone.

42 students can contact **Christopher Nah / hnah on the global 42 Slack**.
Everyone can [open a GitHub issue](https://github.com/CrispyNuggetD/42sg-campus-lan/issues/new)
with a proposal, question or feedback. GitHub is the public contact route; email
notifications depend on each account’s settings. Never post API credentials,
private student data or personal logs in an issue. Discuss substantial changes
before investing time; the [contributor workflow](../AGENTS.md) explains project
conventions. Proposals remain open to revision, not delivery promises.

## Next proposed milestone: frontend and usability

Explore a [Textual-based frontend](frontend-milestone.md): a consistent LAN42
terminal design, clearer guest/sign-in/host states, discoverable actions and
keyboard-first workflows. This is also Christopher’s frontend engineering
learning milestone. Start small with Textual; the [appendix](frontend-milestone.md#appendix-architecture-considerations-and-future-learning)
records the shared-service API idea and other ecosystems as future learning
options, not initial implementation scope. V3 beta is a working candidate, not a reserved release
number; scope, compatibility and validation determine graduation.

## Reliability and hosting

[Campus features currently depend on an approved on-campus host](campus-guide.md).
Explore more dependable availability while preserving the owner’s Singapore-only
policy, authentication, data minimization and explicit host enrollment. An
always-on or offsite deployment is not an existing service guarantee. First
clarify campus/network constraints and operating responsibility; this is an open
problem, not a selected hosting architecture.

## File-sharing review

KoelDrop already retains versions. A [Git-style text diff/review viewer](file-sharing-design.md)
is a possible later UI improvement, not a shipped feature. Explore how to make
changes understandable without weakening per-file receive/deletion consent.

## Possible milestone: Life OS × LAN42

Explore connecting LAN42 with Christopher’s separate project, provisionally
named **Life OS**. The current direction is to evaluate running an LLM on the
service host, rather than relying on a separate personal computer. Hardware,
hosting location, access and deployment remain undecided.

The experiment combines **gamification, fun and social interaction** with the
“deadfishes” theory described in the Life OS project’s whitepaper. It is broader
than a token-usage or environmental dashboard: token estimates are already
possible, while the proposed experiment asks how the experience and incentives
might shape participation. This is a motivation to explore, not a demonstrated
result or a claim that AI use is environmentally beneficial.

Before a pilot:

- Recalculate electricity use and environmental impact for the actual host,
  model, idle time and expected workload. Distinguish measured consumption from
  estimates; token counts alone do not establish energy use or emissions.
- Define the gamification and social experiment from the whitepaper, including
  what participation means and how outcomes would be evaluated.
- Decide consent, data retention, access controls, resource limits and separation
  from LAN42’s existing campus API service before introducing LLM features.

No LLM service or Life OS integration is currently provided by this milestone.
The AI development/learning disclosure in the README describes how the existing
project is built; it is separate from this proposed product expansion.
