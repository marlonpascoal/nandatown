# `catalog_size` is declared, documented, and never read

**Scenario:** `marketplace`
**Setting changed:** `task.config.catalog_size`
**Result:** no observable effect at any value. The knob has no consumer anywhere in the codebase.

---

## Hypothesis, written before running

`catalog_size: 200` is the one knob in `scenarios/marketplace.yaml` whose effect I could not predict from its name. `rounds` obviously scales the run and `message_drop` obviously degrades delivery, but catalog size sits between the agents and the structure of the market, so I expected it to matter.

I predicted that raising it to 2000 would spread 50 buyers across more distinct products, reducing contention for the same items and changing the matching pattern visible in the trace. I planned a second run at `catalog_size: 5` to test the opposite direction.

## Evidence

| Configuration | Trace lines | md5 | Changed? |
|---|---|---|---|
| baseline, `catalog_size: 200` | 2200 | `e69c7730efd9285b4670798f22b45dad` | — |
| `catalog_size: 2000` | 2200 | `e69c7730efd9285b4670798f22b45dad` | no |
| `catalog_size: 5` | 2200 | `e69c7730efd9285b4670798f22b45dad` | no |
| `rounds: 10 → 30` | 5832 | `06b8d7129ce27a8fa5c255d6f67c4fcf` | yes |
| `failures.byzantine_agents: 0.30` | 674 | `725050142d5b7a0b6d19666696a215ae` | yes |

The trace is byte identical across a 400x range of `catalog_size`.

The last two rows are the point of the table. They are controls, one from each of the two blocks this exercise permits to be changed. Both move the trace. So the null result is a property of `catalog_size`, not a mistake in how I configured the run.

## Seed invariance

The result above is at `seed: 42`. Since the finding is that the knob has no
consumer, it should hold at any seed, but it is cheap to check rather than argue.

| seed | `catalog_size: 200` | `catalog_size: 2000` | identical |
|---|---|---|---|
| 7 | `c09e4544576b…` | `c09e4544576b…` | yes |
| 1234 | `5b302c6bae6d…` | `5b302c6bae6d…` | yes |
| 99991 | `13421447def7…` | `13421447def7…` | yes |

The hashes differ across seeds, which is what makes the comparison meaningful:
the seed does move the trace. `catalog_size` does not, at any of them.

## Investigation

```
$ grep -rn "catalog_size" --include=*.py --include=*.yaml --include=*.md .
scenarios/marketplace.yaml:35                              declares it
packages/.../scenarios_builtin/yaml/marketplace.yaml:35    declares it
packages/nest-core/nest_core/scenario.py:92                default inside a TaskConfig constructor
docs/writing-a-scenario.md:55                              uses it as the worked example
```

Four occurrences, no consumer. `marketplace_factory` confirms it:

```python
# packages/nest-core/nest_core/scenarios_builtin/marketplace.py
336:    task_config = config.task.config
337:    rounds = task_config.get("rounds", 10)     # reads rounds, and nothing else
```

The parameter is declared in two scenario files, hardcoded as a default in a constructor, and taught in `docs/writing-a-scenario.md` as the canonical example of *"task-specific knobs, free-form dict"*. No code reads it. There is no warning and no validation error.

## How widespread is this?

Rather than stop at one knob, I wrote `scripts/check_orphan_knobs.py`. It parses every scenario YAML, collects each key under `task.config` and `failures`, and searches `packages/` for a consumer using the two access patterns the codebase actually uses: `task_config.get("x")` and `failures.x`.

```
$ python scripts/check_orphan_knobs.py
Declared knobs across scenarios/*.yaml : 49
With a consumer in packages/           : 47
Orphaned (declared, never read)        : 2

  catalog_size             declared in: marketplace
  victim                   declared in: attested_peering
```

Two out of forty-nine. This is a small problem today rather than a systemic one, and I would rather state that precisely than overstate it. `--strict` exits 1 so the check can run in CI and keep the number at zero.

## Why this matters here specifically

Nanda Town's premise is that it tells you whether your protocol actually works. A configuration key that is declared but never read is the quietest way for that premise to fail, because it manufactures a clean-looking null result: the run succeeds, the trace validates, and the experimenter records a variable as tested that was never varied.

Type checking does not catch it, because task config is a free-form dict by design. `pytest` does not catch it, because the tests assert on outcomes rather than on whether an input was consumed. The trace looks fine. It is a false negative wearing the costume of a clean experiment.

## What I would build next

Extend the check from *declared but never read* to the harder and more common case: *read, but with no observable effect on the trace*. A fuzzer that perturbs one knob at a time across its plausible range and reports which knobs never move the output would cover both cases.

## Files in this PR

| Path | What it is |
|---|---|
| `examples/orphan-config-knobs/marketplace_catalog2000.yaml` | the experiment |
| `examples/orphan-config-knobs/marketplace_catalog5.yaml` | opposite direction |
| `examples/orphan-config-knobs/marketplace_rounds30.yaml` | control, `task.config` |
| `examples/orphan-config-knobs/marketplace_byz30.yaml` | control, `failures` |
| `scripts/check_orphan_knobs.py` | the generalised check |

Traces are not committed, since `traces/` is gitignored. The md5 values above are reproducible from the YAMLs in about thirty seconds.

## Reproducing

```bash
nest run scenarios/marketplace.yaml
nest run examples/orphan-config-knobs/marketplace_catalog2000.yaml
nest run examples/orphan-config-knobs/marketplace_catalog5.yaml
nest run examples/orphan-config-knobs/marketplace_rounds30.yaml
nest run examples/orphan-config-knobs/marketplace_byz30.yaml
md5 traces/*.jsonl        # md5sum on Linux
python scripts/check_orphan_knobs.py
```

## Tools and help

Claude (Anthropic's Cowork) as the main coding and research agent, and Cursor as the editor. I ran every scenario and inspected every trace myself. Repository documentation read directly: `README.md`, `CONTRIBUTING.md`, `docs/writing-a-scenario.md`.
