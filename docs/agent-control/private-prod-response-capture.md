# Private PROD-01 response capture

The Founder may explicitly enable one private response capture for the
Founder-run ATS-1201 command:

```text
python3 -B -m tools.agent_control.prod_first_live \
  --expected-source-commit <FOUNDER_REVIEWED_COMMIT> \
  --private-response-capture
```

The capture is off by default. It writes only the already bounded,
decompressed provider response body to `/var/tmp/bonup-prod-diagnostic/`.
The directory is owner-only and each generated file is created exclusively
with mode `0600`. The command makes one request with zero retries, redirects,
or tools.

The Founder may inspect the generated file directly on the VPS with narrow
local commands. The raw file must not be pasted into ChatGPT or Codex,
uploaded, committed, emailed, or logged. It must not be sent to chat/Codex.

After diagnosis, remove generated capture files with:

```text
python3 -B -m tools.agent_control.prod_first_live \
  --cleanup-private-response-capture
```

Cleanup unlinks generated files and verifies that none remain. It does not
claim guaranteed forensic secure deletion on modern filesystems.
