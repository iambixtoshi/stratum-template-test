# AntPool & Friends audit

This repository tests two separate questions:

1. **Template control:** Does Luxor publish the same Bitcoin block templates as AntPool?
2. **Treasury control:** Do mature Luxor and AntPool coinbase rewards consolidate into the same transaction or address graph?

Neither result substitutes for the other. A pool may build independent templates while sharing custody, settlement infrastructure, or FPPS financing.

## Reward-cluster audit

`reward_cluster_audit.py` compares three cohorts:

- `pre_change`: 2023-09-08 through 2023-12-06
- `post_change`: 2023-12-08 through 2024-03-07
- `current`: the latest rolling 90 days

For each cohort it samples mature Luxor and AntPool coinbases, records every destination encountered, and traces likely treasury/change outputs for up to five hops. It reports:

- direct transactions containing both Luxor and AntPool coinbase inputs;
- shared transaction nodes;
- shared addresses at the same or different depths;
- the exact graph paths and pruning decisions in the raw JSON.

The bounded traversal stops recursively following transactions with more than 50 outputs and follows at most three high-value outputs per transaction. All encountered destinations remain recorded. This prevents miner payout fan-outs from being misclassified as thousands of treasury branches.

Environment controls include `LUXOR_LIMIT`, `ANTPOOL_LIMIT`, `MAX_HOPS`, `FANOUT_STOP`, `MAX_RECURSIVE_OUTPUTS`, `MIN_VALUE_FRACTION`, and `AUDIT_PERIODS`.

## Authorized Stratum monitor

`stratum_monitor.py` requires a valid Luxor observer worker because Luxor sends only an initial public job before rejecting an unknown username.

Configure these GitHub repository secrets:

- `LUXOR_USER`, for example `account.observer`
- `LUXOR_PASSWORD`, normally `x` unless the account requires another password

The scheduled workflow then collects Luxor and AntPool jobs simultaneously and commits timestamped raw comparisons under `results/stratum/`.

## Interpretation

| Templates | Reward graph | Interpretation |
|---|---|---|
| Shared | Shared | Strong evidence of both template and treasury linkage |
| Independent | Shared | Independent block construction with shared custody, settlement, or financing |
| Shared | Separate | Shared template provider with a separate observed treasury route |
| Independent | Separate | No connection detected in the tested windows and graph depth |

A negative graph result does not prove separate ownership. Rotating deposit addresses, a common custodian assigning separate addresses, or convergence beyond the configured hop depth can hide an economic relationship.
