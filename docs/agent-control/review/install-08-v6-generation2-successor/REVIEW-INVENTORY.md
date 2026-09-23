# bonUP PROD-01 Generation-2 successor candidate

This inventory is informational. The canonical successor bytes at
`generation2-successor.json` are the review subject. No Genesis, approval,
installation, or activation is represented here.

## Candidate identity

- Generator source: `tools/agent_control/successor_generation.py`
- Repository HEAD: `5edc95a3fb5027bd830f7f28e74b39dc35eaa472`
- Successor schema version: `1`
- Successor type: `PROD01_GENERATION2_SUCCESSOR`
- Provisioning generation: `2`
- Canonical candidate digest (SHA-256 including final newline): `e92cd0ca5245f62499899ac4fbbafbae260488912b550f142159e33e107051f2`
- Successor bundle digest: `cf7d0a911e8417e2da6edf9be7fbae822906c6827b3d36aedcec0e906e36688b`
- Approval state: `approved=false`
- Activation state: `activation=false`
- Integration-services state: `integration_services_approved=false`

## Exact Generation-1 predecessor

- G1 candidate: `docs/agent-control/review/install-07-v6-current-head/`
- G1 manifest digest (SHA-256 of canonical bytes including final newline): `d96adc1e59aab2f868ad8450c300996d80cf7fc8b42df1f63416c822a494dd20`
- G1 bundle digest: `22dd0fc6c763b925711b650ab8ec6fa1a0db6ff9871e9d2dfeb584a5b3b23608`
- G1 source commit: `4296301466f05ca0b479b1c802b7b1d4b15f1be8`
- G1 product-scope digest: `e0f74232363cd81180d7e75d964bd0c6bed3d391e7d3ffdc7d40579b8f577e46`
- G1 runtime-module digest: `6ea80b34af85e2ae03721427b01c5b60cf5bfc84d1bdfa03f7fc0b2fc6ad3454`

## Preserved runtime binding

- Runtime source commit: `4296301466f05ca0b479b1c802b7b1d4b15f1be8`
- Product-scope digest: `e0f74232363cd81180d7e75d964bd0c6bed3d391e7d3ffdc7d40579b8f577e46`
- Runtime-module digest: `6ea80b34af85e2ae03721427b01c5b60cf5bfc84d1bdfa03f7fc0b2fc6ad3454`
- Fixed pre-Genesis Founder policy: present; no public key or signature

## Validation state

- Deterministic regeneration: passed
- Exact predecessor validation: passed
- Existing Genesis candidate structural validation: passed
- Genesis ceremony: not performed
- Founder key/signature: absent
- Installation approval: absent
- Provisioning/activation: not performed
