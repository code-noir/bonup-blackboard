# bonUP proposed installation approval — NOT AUTHORIZED

`proposed-approval-stage.json` is deterministic review output. Its nested
`installation_manifest` and `installation_inventory` define the proposed approved
representation. The top-level binding records their byte digests and the exact
committed candidate identity.

No founder decision is present. Do not install the nested manifest merely because
it contains `approved=true`. A later explicit authenticated INSTALL_ONLY decision
must approve the entire envelope. Activation and service startup remain false.

The historical candidate at `../m3-generation-1/` remains unchanged. See
`../../installation-approval.md` for the transformation, receipt and hash rules.
