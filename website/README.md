# LAN42 website

The shareable home (`index.html`) is a one-minute student starter, not a command
encyclopedia. `website/home.html` defines its short journey; `build.py` injects
the installation snippet, contributor entries and optional AI disclosure from
README.md. Keep those shared facts canonical in the README. Curated home copy
must match current behaviour and stay short; do not put every feature here.

`handbook.html` keeps its old URL but is now the **User guide**, generated from
`docs/README.md`. Its topic links open matching Markdown-generated HTML pages.
`commands.html` contains the full searchable reference, built from the same
self-contained `docs/quick-guide.html` opened locally by `/help`. The offline
file and terminal command behaviour are unchanged. `roadmap.html` is the plans
and collaboration entry point. The main GitHub README remains a useful repository
introduction, not a second website homepage. No private data goes into the site.

Build locally:

```sh
python3 -m venv /tmp/lan42-web
/tmp/lan42-web/bin/pip install -r website/requirements.txt
/tmp/lan42-web/bin/python website/build.py
python3 -m http.server 8080 --directory _site
```

Open http://localhost:8080. Build output is ignored.

When terminal HELP changes, run `python3 website/build.py --refresh-guide` to
refresh its generated section in the offline guide. Hand-edit the guide's
curated command cards when behaviour changes; leave its generated block alone.
The Pages build also regenerates the current HELP block directly from the app's
AST without importing or starting the app. Run `test_website.py` after changes.

The Pages workflow rebuilds the site from the latest guide and README on every
main push. One-time owner setup: repository Settings → Pages → Build and
deployment → Source: **GitHub Actions**. Then rerun **Publish LAN42 guide** in
Actions (or push a new change). No token or private key needs to be added.

Expected public URL: https://CrispyNuggetD.github.io/42sg-campus-lan/
The `deploy` job reports the final live URL. Until Pages is enabled, GitHub can
build the artifact but will reject deployment; do not describe the URL as live.

## Branded small pages

Use `templates/page.html` and `page.css` for new standalone credit, milestone or
information pages. They follow the README/guide identity: **LAN42 BETA**, “Good
company. A few good commands.”, navy `#13293c`, mint `#a8e6cf`, pale background
`#eef3f7`, system fonts and rounded cards. Use Christopher Nah / hnah for current
public attribution. Keep historical names inside clearly labelled archives.

`alpha-tester.html` is an authored **content fragment**, not a standalone server
page. In `build.py`, call `branded_page(title, description, fragment)` and write
its output under the desired public filename. The renderer escapes metadata and
inlines the shared CSS; content fragments are trusted repository HTML, never
untrusted user input. Keep fragments semantic: one h1, labelled sections, visible
link text, accessible status messages, responsive cards and a usable no-script
fallback. Reuse `.hero`, `.eyebrow`, `.cards`, `.card`, `.label`, `.button`, `.muted`
and `.note` rather than copying page styles.

The offline command guide remains self-contained. README provides shared home
installation/credits/disclosure; docs/README.md and topic Markdown provide user
documentation. Do not maintain a second manual HTML copy of those sources. Build and preview the generated page, then run `test_website.py`. Avoid
new trackers, remote fonts or decorative dependencies. Darren’s page preserves
the existing GitHub account-ID lookup and last-known-profile fallback.

## Roadmap pages: Markdown is the source

`docs/roadmap.md` generates `roadmap.html`; `docs/frontend-milestone.md` generates
`frontend-milestone.html`. Both use the shared branded page shell, a generated
contents list and responsive document layout. Relative links between these plans
become local HTML links; other documentation links lead to their GitHub source.
Edit the Markdown, not generated `_site` files or a second HTML copy. Every main
push rebuilds both automatically. Keep statuses, collaborator-sized tasks and
known limitations current when plans change or features ship. Add further
published plan documents to `DOCUMENT_PAGES` in `build.py` and the output/link
checks in `test_website.py`.

## Topic guides and navigation

`DOCUMENT_PAGES` maps canonical Markdown files to public HTML paths. Its links
are resolved relative to each Markdown source, keeping mapped topics within the
website and other sources on GitHub. README section anchors retain GitHub targets
rather than pointing to unrelated homepage sections. Plans and help share the
brand shell, but use different introductory language. `handbook.html` is always
labelled User guide; never reintroduce the sequential README mirror.

When behaviour changes, update the relevant topic Markdown and concise home copy
if it affects basic use. README credit entries and AI disclosure flow to home
automatically. Keep contributor, roadmap, source and help links discoverable.
Build and check both beginner and reference journeys; preserve the offline HELP
generation check. Python/docs/site changes here alone do not bump server version.

Command search presents matching rows immediately below its input, with a live
count, nearby empty state and Clear/Escape reset. Keep results visible without
scrolling through introductory material; cloned command rows retain copy actions.
Check both narrow and desktop widths when changing this interaction. The same
self-contained file powers the online reference and local help.
