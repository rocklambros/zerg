# Validated Design: ZERG Website

## Scope (Confirmed)
Single-page landing site replacing MkDocs. Pure HTML/CSS/JS with Tailwind CDN. Deployed via repurposed docs.yml workflow to GitHub Pages.

## Sections (Confirmed, in order)
1. **Hero** — Commanding headline + 3 glass pillar cards (Security, Containers, Parallelism) + pip install CTA
2. **Why ZERG** — Problem→solution narrative (manual setup vs automated)
3. **How It Works** — Plan→Design→Rush→Merge flow visualization
4. **Commands Cheat Sheet** — Table of all /zerg: commands with one-liners, link to wiki
5. **Quick Start** — pip install + 4 core commands with copy-to-clipboard
6. **FAQ** — Expandable accordion
7. **Footer** — GitHub, wiki, sponsor, license links

## NFRs (Confirmed)
- Dark-first design WITH light mode toggle (sun/moon icon in nav)
- Mobile-responsive
- No JavaScript frameworks (vanilla JS only)
- Page load under 2s
- Accessible (WCAG AA)
- SEO meta tags + Open Graph

## Visual Style
- Dark navy background with purple/green Zerg-inspired accents (subtle nods, not immersive)
- Glassmorphism cards (frosted panels, semi-transparent borders)
- Top navigation bar with dark/light toggle
- Gradient accent text for emphasis
- Staggered fade-in scroll animations
- Code blocks with copy-to-clipboard
- FAQ accordion with smooth expand/collapse
- Stat counters for key metrics

## YAGNI Gate
All features kept — zero deferred.
