# Experimental roadmap

[← Project introduction](../README.md) · [Documentation contents](README.md)

These are possible project expansions, not release commitments or available
features. Scope and feasibility may change; no delivery date is promised.

## Next proposed milestone: frontend and usability

Explore a [Textual-based frontend](frontend-milestone.md): a consistent LAN42
terminal design, clearer guest/sign-in/host states, discoverable actions and
keyboard-first workflows. This is also Christopher’s frontend engineering
learning milestone. V3 beta is a working candidate, not a reserved release
number; scope, compatibility and validation determine graduation.

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
