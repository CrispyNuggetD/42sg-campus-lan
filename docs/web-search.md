# Web search and LAN42's impact counter

[← LAN42](../README.md) · [All guides](README.md) · [Personal preferences](preferences.md)

- [Choose your engine](#choose-your-engine)
- [The permanent counter](#the-permanent-counter)
- [Privacy and limits](#privacy-and-limits)
- [The little 4](#the-little-4)

## Choose your engine

```text
/search your search terms
/settings search
/settings search ecosia
/settings search google
/settings search custom https://example.com/search?q={query}
/settings search counting off
/search stats
```

Ecosia is the default. LAN42 opens an explicit search URL using your default
browser; it does not read browser profiles, discover/change that browser's own
search-engine setting, or inspect existing tabs. Custom engines require one
`{query}` placeholder in a fixed-host HTTPS URL's query string. Search terms are
encoded as data, not executable commands or extra URL parameters.

Ecosia says it dedicates all profits to climate action, primarily tree planting.
Its results and ads come from Bing, Google and EUSP depending on availability;
it is not simply a Google wrapper. There is no promise of a tree per search.
See Ecosia's [funding explanation](https://support.ecosia.org/article/33-how-does-ecosia-make-money),
[search providers](https://support.ecosia.org/article/579-search-results-providers)
and [privacy policy](https://www.ecosia.org/privacy). Checked 27 October 2026.

Choosing Google offers one confirmation with a short invitation to consider
Ecosia. Yes saves Google; Enter keeps the current engine. Once chosen, Google
works without repeated persuasion. Browser launches still respect inherited
browser/`search` popup consent. Use `/settings permissions search ask|allow|deny`
to control them separately. All current and future app search hooks should use
the same engine setting.

## The permanent counter

This is Christopher's FOSS usage-impact counter for LAN42, not an Ecosia-issued
verification or a measurement of trees planted. `/search stats` and
`/settings search` show the available host's aggregate. The two figures are:

1. **Ecosia launches reported to the host:** one accepted report after the local
   browser API accepts a launch. Repeating the same search increases this total.
2. **Estimated unique search URLs:** repeated normalized queries contribute to
   the same compact uniqueness sketch across clients. This is an estimate, not
   a stored list of links. Whitespace is normalized; query case/quotes are retained.

Counting is **on by default**, with a persistent per-computer opt-out:
`/settings search counting off`. It can be restored with `... counting on`.
Google and custom-engine launches are excluded. Counters live in the host's
private configuration, survive normal restarts and package updates, and are
never automatically committed to GitHub. Aggregates do not expire. Host backups
need both the private database and its key; a missing key disables counting
instead of silently changing the meaning of retained uniqueness data.

Search opens before any reporting request. If the pinned host is unavailable,
search still works; there is no guessed increment, offline query queue or later
history upload. The count therefore covers accepted reports, not every possible
LAN42 search. Browsers cannot prove completion of a search, ad view, result click,
revenue or climate impact. Modified clients can submit inaccurate reports;
bounded rate/replay checks reduce accidental duplicates and spam, not provide
independent attestation. The UI deliberately avoids “verified searches”.

## Privacy and limits

LAN42 does **not** persist raw search terms/URLs, an enumerable query-hash set,
per-user contributions, identities, timestamps per click or result-click history.
`/search`, `/key4` and `/settings search ...` are excluded from local command
history; older matching entries are removed when that history loads.

The client sends an SHA-256 fingerprint of its canonical search URL and a random
replay nonce over the existing pinned TLS connection. **No account/session,
login or user ID is included.** The host uses a private HMAC key to update a
4096-register HyperLogLog sketch and a cumulative integer in SQLite. It does not
store the submitted fingerprint or nonce. Source-rate keys live in RAM for one
minute; replay keys for five minutes, without a query association. All that
persists is the aggregate and its private key—not who clicked what.

The uniqueness sketch uses about 4 KiB and has a typical relative standard error
of approximately 1.6%, rather than exact uniqueness. See the original
[HyperLogLog paper](https://algo.inria.fr/flajolet/Publications/FlFuGaMe07.pdf).
No browsing history can be enumerated from an app query-list because none exists.
This is not an anonymity guarantee against a modified/monitoring host: the host
still sees a connection source and transient report, and the browser/search
provider receives the real search terms and may keep its own history.

Merged permanent aggregates cannot subtract one person's old contribution.
Opting out stops future reports. `/search forget` explains this distinction; it
cannot pretend to erase an individual record that was never retained. Browser
and search-provider history remain subject to their own controls.

The aggregate endpoints expose only counts and accept bounded reports. They do
not call the 42 API, require a student identity, grant roles, change host trust,
proxy searches or open another port. Existing campus API admission stays separate.

## The little 4

F5 still toggles output volume. Its first use reveals a security-history joke
and a separate clickable **[4?]** footer button. That button (or `/key4`) searches
for the eMudhra “private key is 4” incident using your chosen engine and normal
browser permission. F5 itself never launches a search.

It references the compromised intermediate certificate's tiny private scalar,
not a LAN42 credential. [Incident explainer and reproduction](https://d4.key64.com/).
