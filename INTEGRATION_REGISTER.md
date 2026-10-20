# Buildwise Repository-Informed Integration Register

**Last reviewed:** 19 October 2026  
**Scope:** Original Buildwise functionality informed by the public repositories supplied for this programme.

## Rule of use

Buildwise does **not** scrape, vendor, or copy a repository merely because it is public. A repository is only a direct code candidate when its licence, maintenance, dependency chain, security posture, and framework fit have been reviewed. Repositories without a root licence are used only for high-level, independently implemented product ideas; no source, plans, drawings, sample assets, datasets, or derived works are brought into this repository.

All current Buildwise workbench calculations are original, deterministic, concept-stage tools. They are not code/permit/engineering/quantity-survey approval.

## Capability register

| Supplied repository | Licence/reuse status found in review | Buildwise capability | Implementation status |
| --- | --- | --- | --- |
| `promiseekeh/seisviz` | MIT | User-supplied, professionally interpreted geotechnical/seismic data visualization workflow | Site/engineering card records that no data is present and prevents inferred soil/seismic conclusions. A data upload/visualization path remains gated behind private-storage and professional-data controls. |
| `GoldenGames18/Plant2Track` | No root licence found | Project progress and plant/delivery tracking pattern | Original per-phase progress tracker with explicit user-entered status/note and duration-weighted dashboard progress. No source copied. |
| `mouadelkbabty/Planification-avec-Contraintes-nerg-tiques` | No root licence found | Energy-aware planning prompts | Original solar-range planner and energy-constrained sequencing prompts, all marked non-electrical-design. No source copied. |
| `Tsuyii/metreai` | MIT | Transparent plan-to-quantity and pricing workflow | Original concept QTO card with visible formula/basis, GHS cost boundaries, and professional QTO disclaimer. No source copied. |
| `leoninnelsontakoudjou/Batibloc` | No root licence found | Block/module planning | Original nominal block-face module calculator with stated 8% planning wastage. No source copied. |
| `EzzaitouniElMehdi/PinIngenierie` | No root licence found | Engineering review workflow | Original project handoff and engineering-review prompts; does not perform structural/seismic design. No source copied. |
| `Chris31-New/OneToolOneBuild` | Empty repository at review | Unified project workspace concept | Buildwise Design-to-Delivery Workbench unifies concept layout, QTO, energy prompts and progress controls. |
| `React-Proto/react-proto` | MIT, stale/wrong stack | Rapid interaction/prototyping pattern | Buildwise uses its own vanilla-JS responsive room-block editor; React Proto source is not integrated because it does not fit this application. |
| `mikeroyal/Photogrammetry-Guide` | Educational guide/resource list | Controlled site-imagery discovery workflow | No photo ingestion is enabled. Any future workflow requires consent, rights, EXIF/PII policy, private storage, malware scanning and human review. |
| `ThatOpen/web-ifc-three` | MIT, maintenance requires renewed review | IFC/BIM web-rendering direction | Buildwise displays its own GLB concept massing today. IFC import/view is deliberately disabled until a maintained viewer and private user-model handling have passed review. |
| `egmalt/house-planner` | MIT | Interactive 2D/3D planning and BOM product pattern | Original editable Design Studio room blocks, regenerated SVG plans, GLB massing and transparent QTO cards. No React/PHP application transplanted. |
| `GSharker/G-Shark` | MIT, C# geometry stack | Computational-geometry product pattern | Original bounded room rectangle normalization, SVG layout rendering and quantity geometry. No C# source integrated. |
| `nomic-ai/aec-bench` | Apache-2.0 | AEC task/evaluation methodology | Buildwise owns deterministic core/API regression tests covering plan, model, schedule, workbench, owner authorization and error boundaries. Benchmark data/assets are not ingested. |
| `jeremylongshore/cad-ai-agent` | Apache-2.0 | Typed, review-first CAD/vector workflow | Buildwise documents immutable-source, confidence and human-confirmation requirements. DXF/vector-PDF upload is withheld until the secure quarantine/review foundation exists. |

## Present user-facing capabilities

- Authenticated project generation, user-scoped projects, SVG plan artifacts, valid GLB concept massing, schedule artifacts, cost CSV, handoff JSON/print sheet.
- **Design Studio:** bounded floor/room blocks, editable labels/types/coordinates/dimensions, persisted project-specific working concept and regenerated SVG layout.
- **QTO/BOM starter:** visible area/wall/roof/concrete allowances and nominal block-module calculation. These are preliminary allowances, never tender or construction quantities.
- **Energy planning starter:** declared energy/solar prompts with a non-design PV capacity range.
- **Delivery starter:** phase-level progress updates, status, notes and duration-weighted dashboard progress.
- **Debug smoke test:** authenticated `POST /api/debug/generate-test` produces fixed-ID plan, GLB and schedule artifacts and reports URLs, byte counts and file-existence status.

## Explicitly not claimed

Buildwise is not currently a replacement for Procore or any enterprise construction-management platform, and it must not claim professional, permit, structural, engineering, quantity-survey, survey, site, code, health-and-safety, payment, or completion authority. The comparison target should be measurable capability acceptance criteria, not an unsupported marketing claim.
