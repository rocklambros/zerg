# Brainstorm Summary: ZERG Website

## Session
- **Domain**: zerg-website
- **Date**: 2026-02-07
- **Mode**: Socratic (single-question)

## Outcome

Custom single-page landing site replacing the broken MkDocs deployment. Pure HTML/CSS/JS with Tailwind CDN, deployed via GitHub Pages.

## Prioritized Feature List

| # | Feature | Priority | Effort | Issue |
|---|---------|----------|--------|-------|
| 1 | Fix GitHub Pages deployment | P0 | Small | #205 |
| 2 | Site structure + hero + 3 pillars | P1 | Medium | #206 |
| 3 | Content sections (Why, How, Commands, Quick Start) | P1 | Medium | #207 |
| 4 | Interactive elements (toggle, FAQ, copy) | P1 | Medium | #208 |
| 5 | Polish (animations, responsive, SEO, OG) | P2 | Medium | #209 |

## Key Decisions
- Replace MkDocs entirely (not augment)
- Tailwind CDN, zero build step
- Repurpose existing docs.yml workflow
- Dark-first with light mode toggle
- Docs link to GitHub wiki (commands cheat sheet on-site only)
- Subtle Zerg theme nods (palette, logo) — not immersive
- Hero: commanding statement + three glass pillar cards
- Visual: dark + glassmorphism + nav bar + deep scroll + animated code + FAQ accordion

## Reference Sites
- ralph-wiggum.ai — dark theme, glass cards, editorial layout, deep scroll
- superclaude.netlify.app — nav bar, light/dark toggle, clean card grid, quick start

## Epic
#204 — https://github.com/rocklambros/zerg/issues/204
