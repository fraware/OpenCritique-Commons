# Novel-concern discovery rates under incomplete references

Unmatched submitted concerns against a **partial natural** or otherwise incomplete
reference set are **novel-concern candidates**, not automatic false positives and
not confirmed discoveries.

## Limits of discovery-rate reporting

1. Discovery rate is undefined until candidates receive independent determinations
   (`confirmed`, `qualified`, `rejected`, or `unresolved`).
2. `unresolved` and `rejected` outcomes do not enter the reference set and must
   not be counted as precision or recall successes or failures arising from
   discovery adjudication.
3. Only `confirmed` (and, when policy admits them into the reference set,
   `qualified`) determinations may create a **successor** benchmark version.
   Historical scorecards and the predecessor benchmark version remain immutable.
4. Reported discovery counts are therefore upper-bounded by adjudication
   throughput and reference completeness, not by matcher unmatched counts alone.
5. Incomplete references systematically understate missed reference concerns and
   can inflate unmatched submitted counts. Public materials must state this
   limitation whenever candidate counts are shown.

## Operational invariants

- Candidates are never edited in place.
- Major and critical candidates require two blinded primary adjudications, with
  at most one tie-break under the novel-determination policy.
- Recomputed scorecards must cite the predecessor scorecard id/hash and the new
  reference-set hash.
