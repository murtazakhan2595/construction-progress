# Landing Page Brief — for a UI generation tool (e.g. Claude Design)

> **Your task:** design and build a single, animated marketing/landing page for
> the web application described below. **You decide the layout, sections,
> components, and interactions** — this brief gives you the *content, story,
> brand, and goals*, not a component list. Make it beautiful, cinematic, and
> credible for an academic + engineering audience.

---

## What this is

A landing page (the "front door") for a **civil-engineering research web app**
that automates construction progress monitoring from drone imagery. The page is
shown to thesis examiners, site engineers, and stakeholders before they enter
the tool itself. It must communicate the **research, the methodology, and the
value** at a glance, and drive people to launch the app.

## The research it represents

- **Thesis:** *"Automating the Project Monitoring System for Roads, Highway, and
  Infrastructure Projects using Machine Learning, AI, Web Application, and
  Digital Twin Techniques."*
- **Researcher:** Zafar Khan (MS thesis).
- **Domain:** road & highway construction monitoring (context: Pakistan; currency
  PKR; example project "N-25 Highway — Lahore–Multan Section").
- **The core idea:** replace slow, subjective, manual site monitoring with an
  automated, objective, geo-accurate pipeline that turns drone photos into
  measured earthwork volumes, costs, and progress — plus a 3D digital twin.

## The methodology to convey (the substance — present it compellingly)

The app runs an end-to-end pipeline. These are the stages (convey them as a
clear story; you choose the visual treatment):

1. **Drone data capture** — before/after aerial imagery of the construction site.
2. **Photogrammetry (WebODM / OpenDroneMap)** — images are reconstructed into a
   3D model: point cloud, Digital Surface Model (DSM), orthomosaic. This is the
   **digital twin** of the site.
3. **Digital Surface Model (DSM)** — a geo-referenced elevation surface of the
   terrain at each survey.
4. **Earthwork volume** — a geo-aware cut/fill calculation differences the
   before/after DSMs to measure how much material moved (m³), with a vertical
   datum ("Z-offset") correction for GCP-less accuracy.
5. **AI road-layer detection** — a custom **YOLO26 segmentation model** detects
   the road construction stage/layer in the imagery (classes: Sub Base,
   Aggregate Base Course, Asphalt).
6. **Bill of Quantities (BOQ)** — the measured volume is multiplied by unit rates
   (PKR) per detected layer to produce a costed bill of quantities.
7. **Progress S-curve + report** — planned vs. actual spend is tracked on an
   S-curve, and the whole analysis is exported as an Excel report.

## Proof points / metrics (use as credibility highlights)

- AI detection accuracy: **mAP50 ≈ 0.96** (segmentation model).
- **3** road-layer classes detected.
- Inference **~5–13 ms** per image.
- Model trained **100 epochs** on **422** annotated images.
- Volume validated against known site quantities (m³-level, Z-offset corrected).
- Photogrammetry runs GPU-accelerated (~8 min per survey).

## Capabilities to surface

Digital-twin 3D reconstruction · AI road-layer detection · geo-accurate earthwork
volumes · automated bill of quantities (PKR) · planned-vs-actual S-curve progress
tracking · one-click Excel reporting.

## Tech stack (optional to show, adds credibility)

Python · Flask · WebODM / OpenDroneMap (ODM 3.5) · YOLO26-seg (Ultralytics) ·
rasterio · OpenCV · matplotlib · Docker.

---

## Brand & design language (match the app it fronts)

- **Typography:** Geist (sans) + Geist Mono (for numbers/metrics), via Google
  Fonts. Use tabular figures for all stats.
- **Accent color:** blue `#2563eb` (hover `#1d4ed8`, tint `#eff6ff`).
- **Neutrals:** slate scale (`#0f172a` … `#f8fafc`). A dark, cinematic hero
  (slate-900/950) is welcome; lighter content sections below.
- **Icons:** Lucide.
- **Feel:** premium engineering-SaaS meets aerospace/survey. Precise, trustworthy,
  not gimmicky. Think a modern GIS / geospatial product landing page.
- **Motion:** tasteful and performant — scroll-reveal, subtle parallax/float,
  count-up metrics, animated connective elements for the pipeline. Respect
  `prefers-reduced-motion`. Nothing that hurts legibility or load.

## Imagery (real aerial/drone construction photography — free to use)

Use these hotlinkable Unsplash photos (aerial roads, construction sites, heavy
earthwork from above). Crop/size as needed via Unsplash URL params
(`?auto=format&fit=crop&w=…&q=80`):

- `https://images.unsplash.com/photo-1487214626629-b7eaa70441b2` — aerial view of a road (great hero).
- `https://images.unsplash.com/photo-1517089472343-85fc51aeb327` — aerial heavy equipment / earthwork.
- `https://images.unsplash.com/photo-1686358244616-aed9e9a1d827` — aerial construction site.
- `https://images.unsplash.com/photo-1687079661575-94c6490e049e` — aerial building/earthwork site.

You may add more from Unsplash in the same theme. Always include a graceful
fallback (a gradient/illustration) so a slow/blocked image never breaks the layout.

## Calls to action

- Primary: **Launch the app** → `/app`
- Secondary: **View past analyses** → `/runs`
- In-page anchors to the methodology/capabilities/results sections as you see fit.

---

## Hard constraints (so it drops into the existing app)

- **One self-contained HTML file** named `landing.html`, served by Flask at `/`.
- **Stack:** HTML + Tailwind (CDN is fine) + vanilla JS. Lucide + Geist via CDN.
  No build step, no framework, no backend calls (the landing page is static;
  only its links point to `/app` and `/runs`).
- Same-origin relative links only. No new backend routes needed beyond serving
  this template at `/`.
- Responsive (desktop-first, must not break on tablet/mobile) and accessible
  (semantic headings, alt text, keyboard-navigable, sufficient contrast).

## Deliverable

Return `landing.html` (plus any notes on where imagery is referenced so it can be
swapped). Confirm the CTAs point to `/app` and `/runs`.
