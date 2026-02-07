# Requirements: ZERG Website

**Status**: APPROVED
**Feature**: zerg-website
**Epic**: #204
**Date**: 2026-02-07
**Prior Art**: `.gsd/specs/brainstorm-website/` (brainstorm, validated-design, research, tradeoffs)

---

## 1. Problem Statement

The current MkDocs-based docs site at `https://rocklambros.github.io/zerg/` needs a custom landing page that communicates ZERG's value proposition — security, containerized parallel execution, context engineering, and token efficiency — in a way that's visually compelling and potentially viral.

## 2. Solution

Single-page landing site replacing MkDocs as the homepage. Pure HTML/CSS/JS with Tailwind CDN. Deployed via repurposed `docs.yml` GitHub Actions workflow. Existing MkDocs documentation remains accessible at sub-paths.

## 3. Scope

### In Scope
- Custom `index.html` landing page (7 sections + sticky nav)
- Dark-first design with light mode toggle
- All 26 commands in cheat sheet table
- 4 glass pillar cards (Security, Containers, Parallelism, Context Engineering)
- Optimized logo (<200KB web version)
- Responsive design (mobile, tablet, desktop)
- SEO meta tags + Open Graph
- Scroll animations
- Repurposed GitHub Actions workflow
- Existing docs content preserved and accessible

### Out of Scope
- Blog or dynamic content
- User accounts / authentication
- Analytics beyond what GitHub provides
- Custom domain (uses `rocklambros.github.io/zerg/`)
- JavaScript frameworks (React, Vue, etc.)
- Build step / bundler / node_modules

## 4. Sections (in order)

### 4.1 Sticky Navigation Bar
- Fixed top bar, semi-transparent background with backdrop blur
- Left: ZERG logo (optimized) + wordmark
- Center: Section anchor links (Why, How, Commands, Quick Start, FAQ)
- Right: Dark/light toggle (sun/moon icon) + **prominent GitHub repo link** (icon + "GitHub" text, not just an icon)
- Smooth scroll to anchors on click
- Collapses to hamburger menu on mobile

### 4.2 Hero Section
- **Tone**: Playful Zerg-themed, viral-worthy, but grounded in real value
- **Headline**: Commanding statement incorporating the swarm metaphor + value props (security, parallel execution, token efficiency). Aim for memorable/shareable.
- **Subheadline**: One-liner explaining what ZERG actually is
- **CTA**: `pip install zerg-ai` with copy-to-clipboard button
- **4 Glass Pillar Cards** (glassmorphism style, frosted panels):
  1. **Secure by Default** — Auto-fetched OWASP rules, language-specific security
  2. **Run Anywhere** — Docker containers, subprocess, or task mode
  3. **Massively Parallel** — Coordinated workers with dependency-aware scheduling
  4. **Token Smart** — Context engineering: 30-50% token savings per worker

### 4.3 Why ZERG
- Compact format: 3-4 bullet pairs (pain point → ZERG solution)
- Example pairs:
  - Manual setup for every feature → Auto-detects stack, fetches rules, generates configs
  - Sequential execution bottleneck → 5+ workers building in parallel
  - Context rot across long sessions → Spec-driven workers, stateless and restartable
  - Token waste on repeated context → Context engineering splits + scoped budgets

### 4.4 How It Works
- Responsive pipeline visualization: horizontal on desktop, vertical on mobile
- 4 stages with icons: Plan → Design → Rush → Merge
- Each stage: icon + title + 1-line description
- Connecting arrows/lines between stages
- Brief explanation of what happens at each step

### 4.5 Commands Cheat Sheet
- Full table of all 26 `/zerg:*` commands
- Columns: Command | Description (one-liner)
- Grouped by category (workflow, utilities, monitoring)
- Link to GitHub wiki for deep documentation
- Searchable/filterable if feasible with vanilla JS, otherwise static table

### 4.6 Quick Start
- 4-step code block with copy-to-clipboard:
  ```bash
  pip install zerg-ai
  /zerg:plan user-auth
  /zerg:design
  /zerg:rush --workers=5
  ```
- Brief annotation per step

### 4.7 Stats / Social Proof
- Feature stats: 26 commands, 3 execution modes, 8 cross-cutting capabilities
- Performance claims: "10x faster feature delivery", "30-50% token savings"
- Displayed as animated counter cards or bold stat blocks

### 4.8 FAQ
- Expandable accordion (details/summary or vanilla JS)
- Smooth expand/collapse animation
- Questions TBD during design phase (cover: install, requirements, pricing, Claude API key, container setup, comparison to alternatives)

### 4.9 Footer
- Links: GitHub repo, Wiki docs, Sponsor, License (Apache 2.0)
- "Built with Claude Code" attribution
- Copyright line

## 5. Visual Style

- **Dark-first**: Dark navy background (#0f172a or similar)
- **Light mode**: Clean white/light gray, toggle via sun/moon icon
- **Accent colors**: Purple (#7c3aed) and toxic green (#22c55e) — Zerg-inspired, subtle
- **Glassmorphism**: Frosted panels with `backdrop-filter: blur()`, semi-transparent borders
- **Typography**: System font stack for body, monospace for code blocks
- **Gradient text**: For hero headline emphasis
- **Scroll animations**: Staggered fade-in on section entry (IntersectionObserver)
- **Code blocks**: Dark background with syntax-style coloring, copy button

## 6. Technical Requirements

### 6.1 Stack
- HTML5 + Tailwind CSS (Play CDN) + vanilla JavaScript
- Zero build step, zero dependencies
- No node_modules, no bundler, no framework

### 6.2 File Structure
```
docs/
  index.html              # Landing page (new)
  assets/
    css/
      custom.css          # Custom styles beyond Tailwind
    js/
      main.js             # Dark/light toggle, copy-to-clipboard, FAQ accordion, scroll animations
    img/
      zerg-logo-web.png   # Optimized logo (<200KB)
      og-image.png        # Open Graph preview image
  commands-quick.md       # Existing (preserved)
  commands-deep.md        # Existing (preserved)
  tutorial-minerals-store.md  # Existing (preserved)
  configuration.md        # Existing (preserved)
  ...                     # Other existing docs
```

### 6.3 Deployment
- Repurpose `.github/workflows/docs.yml`
- Change build step: replace mkdocs build with simple file copy/upload of `docs/`
- Update path triggers to include `docs/**` (already present)
- Remove mkdocs.yml trigger (or keep for backward compat)
- Upload `docs/` as pages artifact instead of `site/`

### 6.4 Logo Optimization
- Source: `logo/zerg_logo.png` (7.6MB)
- Target: `docs/assets/img/zerg-logo-web.png` (<200KB)
- Resize to max 400px width for web display
- Compress with quality optimization
- Generate separate OG image (1200x630) for social sharing

## 7. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Page load (mobile 3G) | < 3s |
| Page load (desktop) | < 2s |
| Lighthouse Performance | > 90 |
| Lighthouse Accessibility | > 95 |
| WCAG compliance | AA |
| Mobile responsive | 320px - 2560px |
| Browser support | Chrome, Firefox, Safari, Edge (latest 2 versions) |
| JavaScript disabled | Content readable, interactive features gracefully degrade |
| No FOUC | Tailwind CDN loaded before render or handled via preload |

## 8. Acceptance Criteria

1. Landing page loads at `https://rocklambros.github.io/zerg/`
2. All 7 content sections render correctly
3. Dark/light mode toggle works and persists via localStorage
4. All 26 commands appear in cheat sheet table
5. Copy-to-clipboard works for code blocks
6. FAQ accordion expands/collapses smoothly
7. Sticky nav scrolls to correct sections
8. Mobile hamburger menu works
9. Existing docs (commands-quick, tutorial, etc.) remain accessible via direct URL
10. Logo loads optimized (<200KB)
11. Open Graph meta tags present and valid
12. Page passes Lighthouse audit (Performance >90, Accessibility >95)
13. No JavaScript framework dependencies
14. GitHub Actions workflow deploys successfully on push to main

## 9. Dependencies

- GitHub Pages enabled on repo (already configured)
- `docs.yml` workflow (exists, needs modification)
- `logo/zerg_logo.png` (exists, needs optimization)
- Image optimization tool (ImageMagick, sharp, or similar — CI or local)

## 10. GitHub Issues (Pre-Created)

| Issue | Title | Priority | Depends On |
|-------|-------|----------|------------|
| #205 | Fix GitHub Pages deployment and repurpose docs.yml | P0 | — |
| #206 | Site structure, nav bar, hero section with 4 pillars | P1 | #205 |
| #207 | Content sections — Why, How, Commands, Quick Start, Stats | P1 | #206 |
| #208 | Interactive elements — toggle, FAQ, copy, scroll animations | P1 | #206 |
| #209 | Polish — responsive tuning, SEO, Open Graph, Lighthouse | P2 | #207, #208 |

## 11. Documentation Impact

- **CHANGELOG.md**: Entry under `[Unreleased] > Added` for custom landing page
- **README.md**: Update docs link if URL structure changes
- **mkdocs.yml**: May be removed or retained as reference only
- **docs.yml**: Modified workflow (significant change, document in PR)

## 12. Open Questions

1. **Headline copy**: Exact wording for viral hero headline (to be drafted during design)
2. **FAQ content**: Specific Q&A pairs (to be defined during design)
3. ~~**OG image design**~~: RESOLVED — Use optimized zerg logo as OG image base (1200x630, logo centered on dark background)
4. **MkDocs removal timing**: Remove mkdocs.yml + pip install in same PR, or separate cleanup PR?
5. ~~**Custom domain**~~: RESOLVED — `zerg-ai.com` planned. OG URLs and meta tags should use `zerg-ai.com` as canonical. GitHub Pages serves as interim until domain is configured.

## 13. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tailwind CDN slow/down | Low | High | Pin CDN version, consider local fallback CSS |
| GitHub Pages cache stale | Medium | Low | Cache-busting query params on assets |
| Existing doc URLs break | Medium | High | Keep all existing .md files in docs/, test URLs post-deploy |
| Large logo causes slow load | High | Medium | Optimize to <200KB, lazy load, use appropriate dimensions |
| FOUC from Tailwind CDN | Medium | Low | Preload link tag, minimal critical CSS inline |
