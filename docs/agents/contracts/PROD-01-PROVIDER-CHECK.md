# PROD-01 Founder-Run Provider Check

> Status: manual pre-live metadata check only
> Authority: **NO INFERENCE — NOT PROD-01 ACTIVATION**

The Founder runs this command directly from an ordinary interactive VPS terminal:

```text
python3 -B -m tools.agent_control.prod_provider_check \
  --expected-source-commit <OWNER-REVIEWED-CHECKPOINT>
```

Replace the placeholder only with the exact commit reported by the completed
checkpoint review. The command first verifies that repository `HEAD` equals that separately reviewed
commit and that both standard input and standard error are interactive terminals.
Only then does it prompt invisibly for the OpenAI API key. It performs at most one
authenticated `GET /v1/models/gpt-5.6-luna`, with a fixed HTTPS host, TLS
verification, disabled redirects and environment trust, zero retries, bounded
timeouts, and a 65,536-byte response limit. It has no Responses or inference path.

Founder procedure:

1. Open an ordinary VPS terminal.
2. Run the reviewed command above.
3. Allow the command to verify the reviewed repository HEAD.
4. At the hidden prompt, type or paste the OpenAI API key.
5. The command performs one model-metadata request.
6. Read the bounded authentication/model-access result.
7. Allow the process to exit.
8. Report only that bounded result to ChatGPT or Codex.

**NEVER paste the API key into ChatGPT or Codex.** Do not place it in argv, an
environment variable, `.env`, a file, or repository content. The implementation
drops Python references promptly but does not claim physical memory zeroization.
