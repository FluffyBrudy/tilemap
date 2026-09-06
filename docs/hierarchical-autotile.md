# Hierarchical Autotile Classification via Distance-2 Signatures

*Research note — tilemap editor autotile system. Status: implemented, 813 passing.*

## 1. Abstract

Grid-template autotiling (3×3 / 4×4 / 5×5) compresses 25 sheet cells into 9
neighbor-pattern rules. Cells sharing a cardinal neighbor pattern collapse
into one rule's variant list, and tile selection degrades to
`random.choice` among positionally distinct pieces — scrambling bordered
motifs (wrong edge segment on a wall run, frozen in place by the
no-re-roll stability guard). We show that **4 additional bits — straight
distance-2 neighbor presence — split every collapsed group of the 5×5
motif into singleton leaves**, recovering exact tile selection with no new
authoring UI. The 9 rules become high-level topology; a per-rule subcase
table maps the extended signature to the exact variant, with legacy random
selection as the backoff for unseen shapes.

## 2. Problem

### 2.1 The 25 → 9 compression

`Standard 5×5 (Cardinal)` assigns each sheet cell the set of filled
cardinal neighbors it would have inside a solid mass
(`autotile_template.py: _cardinal_grid_mappings`). Cells with equal
neighbor sets merge into one `AutotileRule` (`apply_template`); at
autotile time the variant is drawn randomly from the merged list
(`layers.py: _autotile_tiles`).

Concretely, column cells 6 / 11 / 16 (sheet positions (1,1), (1,2),
(1,3)) all carry pattern `{U, L, R, D}` and collapse — with six further
interior cells — into a single 9-variant tuple. A wall tile entitled to
piece 6 may receive 11 or 16 by dice roll, and the stability guard
("keep current variant if already in the set") then preserves the wrong
answer across re-autotiles.

### 2.2 The real question

Not "how do I choose the correct random index?" but:

> **What information must survive the 25 → 9 compression for the visual
> tile to remain uniquely determined?**

The system conflated two meanings in one bucket: interchangeable
*style* variants (mossy rock A/B/C — random is correct) and
*positional* pieces (edge-start / middle / end — random is wrong), with
nothing recording which meaning applies.

## 3. Prior art surveyed

- **Tiled**: general solution — arbitrary pattern matching. Maximally
  expressive, maximal authoring burden.
- **Unity (RuleTile)**: explicit ordered predicates with expandable
  neighborhoods. Expressive; tedious by design.
- **Godot terrain**: defines which neighborhood distinctions are
  meaningful for the blob case. Closest in spirit; demands strict
  Wang-style tileset discipline, judged infeasible here.
- **This work**: neither 25 independent rules nor 9 rules + random, but
  a **hierarchical classifier** — 9 topology nodes refined by the
  minimal discriminating bits into ~25 exact leaves. The hierarchy
  lives in the *matching* (topology → subcase → backoff), not in rule
  count.

## 4. Method

### 4.1 Signatures, computed identically on both sides

Each tile is described by `(cardinal4, dist2-4)`:

- `cardinal4` — presence of filled same-group neighbors at distance 1
  (pre-existing).
- `dist2-4` — presence of filled same-group neighbors at straight
  distance 2 in each cardinal direction (new; 4 extra lookups per tile).

Motif side (template apply): motif bounds act as the mass
(outside-motif = absent), mirroring off-map semantics at classify time,
so motif-derived and map-derived signatures agree on motif-shaped
masses by construction. Map side (classify): same-group-scoped
presence, consistent with the existing membership rule
(`autotile_group` field, else legacy variant lookup).

### 4.2 Subcase tables

`AutotileRule.subcases: {frozenset(dist2): [vids]}`. Template apply
files each cell under its motif-side signature; map-side classify
looks the signature up. Empty table = legacy behavior, so old sidecars,
hand-authored rules, and genuine style variants are unaffected.

### 4.3 Backoff matching

Cardinal rule (most-specific-first, unchanged) → subcase leaf (exact;
singleton leaves assigned deterministically, multi-vid leaves keep
`random.choice` — the one place randomness remains legitimate) →
on signature miss, rule-level random as before. Unseen shapes degrade
to status quo, never worse. The matcher is shared by full-layer and
paint-time paths, so both gain exactness together.

### 4.4 Group scoping

Distance-2 offsets are registered per group (`extended_by_group`,
union of subcase-key offsets), mirroring the existing
`offsets_by_group` pattern: groups that never learned subcases neither
compute nor match on the extended bits.

### 4.5 Procedural consequences (verified, not assumed)

Running the motif signature table over the 5×5 grid:

| cardinal pattern | cells sharing it | distinct dist2 sigs | singleton leaves |
|---|---|---|---|
| full `{U,L,R,D}` | 9 | 9 | yes |
| 4 edge patterns | 3 each | 3 each | yes |
| 4 corner patterns | 1 each | 1 each | yes |

9 rules → 25 exact leaves. Edge triples resolve to start / middle /
end (continuation bits); the interior 9 resolve by thickness (distance
to mass edge per axis). No diagonal bits required for the blob case;
concave corners remain a documented separate limit.

### 4.6 Acceptance property

**Round-trip**: a painted exact 5×5 motif classifies every cell back to
its own sheet vid; re-autotile is a zero-change no-op. Longer runs
resolve positionally (7-wide wall → start / middle / end pieces);
shapes no motif described fall back without error.

## 5. Complexity

Per tile: 4 extra same-group lookups beyond the existing 8-neighborhood
scan; subcase lookup is a frozenset hash. Rule-cache hash extended to
include subcase tables so edits invalidate correctly. No asymptotic
change to full-layer or paint-time passes.

## 6. UI position

Deliberately zero new interface: same template-apply button, same
paint keys. The extended machinery is data + matching, both invisible —
distance-2 presence is a fact about the neighborhood, not a setting.
The sole visible change is the variant-count badge flipping from `x9`
to `9 exact` when a rule fully disambiguates, turning the previously
alarming 9-tuple display into evidence the system resolved it. A
correct engine behind the existing panel reframes that panel from
"underpowered" to "sufficient," and avoids the run-direction controls
and fallback pickers a positional-run alternative would have required.

## 7. Interaction log (technical spine)

1. Friction report: draft commit exits draft mode every time
   (D → paint → Enter → D loop). Scoped fix: `Shift+Enter` =
   commit-and-continue (planned, unimplemented).
2. Variant-collision question → established: variant namespace is
   sheet-global; cross-group reuse resolves silent first-wins
   (`layers.py`, `autotiler.py`, template collision popup excepted).
3. Stamp composer has no group picker and no variant mapping (raw
   1:1 captures; no `autotile_group` stamped). Added: `StampRule.group`
   + composer cycle control + applier stamping (stashed; conflicts
   pending on pop).
4. Shortcut separation shipped to plan: `Ctrl+A` = stamps,
   `Ctrl+Shift+A` = autotile (stashed).
5. "Learn from the map" proposal (draw the result → select/commit →
   Learn Pattern dialog → Entire/Boundary mask → live stamp).
   Implemented with 34 tests (stashed).
6. Stamp-does-nothing report → root-caused to per-map sidecars: the
   stamp lived in `temp.stamps.json` while `level1.json` was open, so
   the session's stamp list was empty; completion's three silent
   zero-paths hid it. Planned: zero-result diagnostics (unimplemented).
7. Border-from-blob question → identified as autotile (5×5 template),
   not stamps: paint the outline, `Ctrl+Shift+A`; absence of paint is
   what keeps middles empty.
8. User's rough estimate (variant tuples 6/11/16; wrong piece picked)
   → confirmed at `autotile_template.py:410-419` (collapse) and
   `layers.py:233-234` (random pick). ChatGPT's hierarchical
   topology/thickness/continuation sketch → verified by signature
   enumeration → implemented as this note describes.
9. Stash incident: two `git stash` runs swept the uncommitted pile
   (draft, stamps, Learn) into `stash@{0}` / `stash@{1}`; working tree
   held only this classifier. Pop will conflict on `layers.py` and
   `autotile_template.py` (different regions; resolvable).

## 8. Open threads (not in this note's scope)

- `Shift+Enter` commit-and-continue.
- Stamp zero-result diagnostics + owning-map name in Learn notices.
- Corners / Custom learn masks; map → reactive-rule generation.
- Diagonal-bit classifier layer (concave corners).
- Pop + merge of `stash@{0}` (draft / stamps / Learn) against this work.
