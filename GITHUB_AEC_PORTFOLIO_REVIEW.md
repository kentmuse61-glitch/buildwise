# Buildwise GH — curated AEC portfolio review

**Purpose:** identify public-repository ideas and components that can improve Buildwise without copying unreviewed source, ingesting third-party plans, or weakening Buildwise's planning-only boundary.

## Operating rule

Buildwise must not scrape or copy whole projects from GitHub or the wider internet. Public availability does not mean every source file, drawing, plan, dataset, trademark, or example asset is usable. Any adopted dependency or substantial code must have a compatible license, a pinned version, a security review, attribution/notice where required, tests, and a deliberate architecture fit.

This review is not a claim that Buildwise is equivalent to, or more capable than, Procore. It is a roadmap toward a focused **Ghana-first design-to-delivery workspace**.

## Decisions from the supplied repositories

| Repository | Relevant capability | License / maintenance signal | Decision for Buildwise |
| --- | --- | --- | --- |
| [`egmalt/house-planner`](https://github.com/egmalt/house-planner) | True-scale 2D planning, 3D, service overlays, BOM concepts | MIT; recent first public release | **Reference and prototype.** Its product scope is most aligned, but it is a React + PHP system whereas Buildwise is FastAPI + vanilla JS. Do not transplant it; build an original compatible Design Studio. |
| [`jeremylongshore/cad-ai-agent`](https://github.com/jeremylongshore/cad-ai-agent) | Typed DXF/vector-PDF analysis/edit workflows, safety/evaluation architecture | Apache-2.0; actively maintained | **High-value architectural reference.** Create an upload-isolated, review-first drawing-intelligence pipeline; never silently alter drawings or imply approval. |
| [`Tsuyii/metreai`](https://github.com/Tsuyii/metreai) | Plan-to-quantity, price enrichment, variant comparisons, PDF/Excel report UX | MIT; latest activity April 2026 | **Reference for a Ghana-specific QTO/BOM workbench.** Build transparent quantity assumptions and source/price dates instead of importing French standards or price claims. |
| [`nomic-ai/aec-bench`](https://github.com/nomic-ai/aec-bench) | AEC task taxonomy and agent evaluation harness | Apache-2.0; latest activity May 2026 | **Use for evaluation methodology.** Build Buildwise-owned golden test cases; separately review dataset/asset terms before downloading any benchmark data. |
| [`promiseekeh/seisviz`](https://github.com/promiseekeh/seisviz) | 2D/3D geophysical visualization | MIT; latest activity September 2026 | **Future optional module.** Only for user-supplied, professionally interpreted geotechnical data; not a site investigation or foundation recommendation feature. |
| [`ThatOpen/web-ifc-three`](https://github.com/ThatOpen/web-ifc-three) | Browser IFC viewing and element/property exploration | MIT, but latest repository activity shown September 2023 | **Do not adopt directly.** Research current maintained IFC viewer packages before an IFC-import milestone. IFC import/export does not make a Buildwise model BIM-authoritative or permit-ready. |
| [`leoninnelsontakoudjou/Batibloc`](https://github.com/leoninnelsontakoudjou/Batibloc) | PDF plan import, scale setting, editable zones, block simulation, quantities | No root license file found; Java desktop implementation | **Feature inspiration only. Do not copy code/assets.** Independently implement calibrated measurement zones after upload security and explicit user scale confirmation exist. |
| [`GoldenGames18/Plant2Track`](https://github.com/GoldenGames18/Plant2Track) | Basic construction-task visualization | No root license file found; latest activity December 2021 | **Feature inspiration only.** Build a modern, owner-scoped schedule, task, dependency, and progress model instead. |
| [`mouadelkbabty/Planification-avec-Contraintes-nerg-tiques`](https://github.com/mouadelkbabty/Planification-avec-Contraintes-nerg-tiques) | Energy/time constrained scheduling exercise | No root license file found; factory scheduling domain | **Do not copy.** Use only the general idea of explicit constraints; evaluate a maintained optimization library separately. |
| [`EzzaitouniElMehdi/PinIngenierie`](https://github.com/EzzaitouniElMehdi/PinIngenierie) | Civil-engineering services site UI | No root license file found; marketing site rather than an engineering engine | **Do not use source/assets.** It cannot confer professional engineering capability. |
| [`GSharker/G-Shark`](https://github.com/GSharker/G-Shark) | General AEC geometry library | MIT, but C# and latest activity shown August 2023 | **Not compatible with the current stack.** Do not add a C# runtime for this. |
| [`React-Proto/react-proto`](https://github.com/React-Proto/react-proto) | UI prototyping | MIT, but latest activity shown January 2019 | **Reject for production.** Its dependency era is too old for the Buildwise frontend. |
| [`mikeroyal/Photogrammetry-Guide`](https://github.com/mikeroyal/Photogrammetry-Guide) | Curated educational photogrammetry resources | Guide, not a production component | **Reference only.** Any future photo/site-capture work needs privacy, consent, storage, accuracy, and professional-review controls. |
| [`Chris31-New/OneToolOneBuild`](https://github.com/Chris31-New/OneToolOneBuild) | — | Repository is empty | **No action.** |

## Execution authorization and delivery order

The product owner authorized **all five capability areas** on 19 October 2026. This is authorization for a staged original Buildwise build, not permission to copy repositories wholesale or to imply professional approval.

The implementation must begin with the shared platform foundation: database migrations and backups, organization/member/project authorization, versioned project data, private artifact storage, audit records, upload quarantine, and browser E2E coverage. Each phase below ships only after its security, data, and acceptance gates pass.

## Recommended Buildwise capability sequence

### Phase 1 — Design Studio (first implementation)

Create an original, owner-scoped interactive 2D concept editor:

- room, wall, opening, and zone entities with explicit dimensions
- snap/grid, undo/redo, selections, layer visibility, and mobile-safe navigation
- live concept SVG + GLB regeneration from a normalized project model
- comparison of saved concept variants
- persistent audit trail of user edits
- unchanged professional/permit boundary language

This takes the useful product direction from house-planner without importing its application.

### Phase 2 — QTO and transparent cost workbench

- user-confirmed measurement zones and quantities
- Ghana-local price catalogue with source, currency, locality, date, confidence, and manual override fields
- side-by-side design/cost/schedule alternatives
- CSV/XLSX/PDF/JSON exports marked as preliminary planning estimates
- explicit exclusions and no construction-ready bill-of-quantities claim

### Phase 3 — Drawing intelligence, review-first

- malicious-file-screened uploads of DXF and vector PDF
- immutable original plus derived, versioned analysis result
- element/line/area inventory with confidence values and human confirmation
- no automatic drawing edits; no DWG upload without a separately evaluated converter and license review

### Phase 4 — Controlled delivery workspace

- organizations, roles, project members, activity/audit logs, issues, photos, document versions, RFIs, change records, and dependencies
- notifications plus task/schedule progress views
- structured professional handoff rather than autonomous professional sign-off

### Phase 5 — Optional interoperability and site data

- maintained IFC viewer research and controlled import only after a data-model decision
- user-supplied site imagery/geotechnical data with consent and accuracy limitations
- benchmark/evaluation harness for every AI-assisted action

## Security, legal, and product gates

1. Do not ingest third-party plans, scraped drawings, copyrighted training data, or repository content without explicit rights and provenance.
2. Treat missing-license repositories as unavailable for code or asset reuse unless the rights holder grants permission in writing.
3. Any uploaded drawing remains private, owner-scoped, virus/file-type screened, size-limited, and immutable in its original form.
4. Every inferred quantity, cost, schedule date, or drawing observation must expose its inputs, confidence/assumption, and review state.
5. Buildwise may be a powerful planning and collaboration product; it cannot truthfully claim professional approval, code compliance, permit readiness, structural safety, or Procore-equivalence without the relevant professional, contractual, and operational systems.
