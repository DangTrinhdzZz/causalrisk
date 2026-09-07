# CLadder v1 sealed-split audit

Audit date: **2026-09-07**

This public-safe report contains aggregate diagnostics and cryptographic checksums only. It exposes no item identifiers, prompts, answers at item level, model identifiers, protected-family identifiers, or split membership.

## Validation verdict

**PASS.** The locally sealed manifests satisfy CLadder split protocol v1.0.

- Immutable archive SHA-256 matched: **yes**
- Canonical candidate pool: **8,917 items**
- Exact split sizes and per-rung quotas: **yes**
- Cross-split item overlap: **0**
- Cross-split canonical-prompt overlap: **0**
- Cross-split protected-family overlap: **0**
- Full-prompt duplicate selected more than once: **0**
- Full-prompt duplicate groups quarantined for audited disagreement: **0**
- Fixed selection seed: `20260905`
- Generator: `scripts/create_cladder_splits.py`
- Auditor: `scripts/audit_cladder_splits.py`

## Aggregate diagnostics

### Smoke

- Items: **60**
- Protected families represented: **36**
- Graph coverage: **9 distinct graph IDs**
- Story coverage: **25 distinct story IDs**
- Sealed manifest SHA-256: `e53e151258e0d71e0f0360e5c8bdd7e1a2e8defa76a34f2774d0f2999776afe9`

| Rung | Total | Yes | No |
|---:|---:|---:|---:|
| 1 | 20 | 10 | 10 |
| 2 | 20 | 10 | 10 |
| 3 | 20 | 10 | 10 |

| Query type | Count |
|---|---:|
| `backadj` | 11 |
| `collider_bias` | 9 |
| `correlation` | 11 |
| `ett` | 4 |
| `exp_away` | 9 |
| `nde` | 7 |
| `nie` | 9 |

### Calibration

- Items: **300**
- Protected families represented: **210**
- Graph coverage: **10 distinct graph IDs**
- Story coverage: **47 distinct story IDs**
- Sealed manifest SHA-256: `45d486f67bf631476aa856abe5a1472201795c200631718e0e6715f9926ae0ca`

| Rung | Total | Yes | No |
|---:|---:|---:|---:|
| 1 | 100 | 50 | 50 |
| 2 | 100 | 50 | 50 |
| 3 | 100 | 50 | 50 |

| Query type | Count |
|---|---:|
| `backadj` | 61 |
| `collider_bias` | 39 |
| `correlation` | 51 |
| `ett` | 7 |
| `exp_away` | 49 |
| `nde` | 40 |
| `nie` | 53 |

### Locked test

- Items: **600**
- Protected families represented: **276**
- Graph coverage: **10 distinct graph IDs**
- Story coverage: **47 distinct story IDs**
- Sealed manifest SHA-256: `e83bd0d6424a653ba42b7fefbfc6cbf59193d46d8bbb7bc58f0076770ca7f7bb`

| Rung | Total | Yes | No |
|---:|---:|---:|---:|
| 1 | 200 | 100 | 100 |
| 2 | 200 | 100 | 100 |
| 3 | 200 | 100 | 100 |

| Query type | Count |
|---|---:|
| `backadj` | 113 |
| `collider_bias` | 87 |
| `correlation` | 137 |
| `ett` | 11 |
| `exp_away` | 63 |
| `nde` | 82 |
| `nie` | 107 |

Graph and story are balancing/coverage diagnostics, not disjointness constraints. The sealed manifests remain local under `data/splits/private/`; their hashes permit reproducibility checks without publishing membership.
