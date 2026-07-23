# Contoso brand guidelines: how the agents use them and how to update them

There are two brand-guideline consumers in this repository, and they read the
guidance completely differently. Understand both before changing the brand
deck.

## The two consumers

| Agent | Source of guidance | Why |
| --- | --- | --- |
| Prompt case-study generator / validator (`agents/prompt/`) | The full `assets/templates/contoso-case-study-template-with-brand-guidelines.pptx` (22 slides), attached directly as a Code Interpreter file during provisioning (see `scripts/provision_prompt_agents.py`) | These agents run in Foundry's managed Code Interpreter sandbox, which can open arbitrary attached files. |
| Hosted case-study agent (`src/km_agents/agents/hosted/case_study_generator/`) | The extracted `assets/templates/contoso-brand-guidelines.md` summary, embedded directly into the agent's instructions text at startup (`main.py`) | The Hosted agent's file-access tool (`FileSystemAgentFileStore`) is sandboxed to `AGENT_WORKSPACE_ROOT` and **rejects any path outside it**, including the brand-guidelines PPTX. The model has no way to open that file at runtime, so a pre-extracted, plain-text summary is inlined into its instructions instead. Validated: `FileSystemAgentFileStore._resolve_safe_path` raises `ValueError` for any path that resolves outside the workspace root.

In both cases, only the **first 8 slides** (the canonical case-study template)
are ever emitted in generated output. The guidance slides (9-22 in the source
deck) are reference material only and must never appear in a customer-facing
deck. This is enforced by:

- Prompt-agent instructions (`agents/prompt/case-study-generator/instructions.md`, `agents/prompt/validator/instructions.md`), which explicitly forbid copying guidance slides into output.
- The Hosted deterministic validator (`validation.py`), which rejects any deck that isn't exactly 8 slides.
- `tests/test_pptx_skill.py`, which asserts the runtime template and generated decks are 8 slides.

## How to update the guidance when the brand deck changes

1. Replace `assets/templates/contoso-case-study-template-with-brand-guidelines.pptx`
   (and the duplicate copy at `src/assets/templates/...`, which the Hosted
   container ships) with the new deck. Keep the first 8 slides identical to
   the canonical case-study template — see `docs/validation.md` for the
   template-compatibility contract if slides 1-8 also change.
2. Regenerate the extracted markdown summary that the Hosted agent reads:

   ```powershell
   python scripts/extract_brand_guidelines.py
   ```

   This writes the same content to both `assets/templates/contoso-brand-guidelines.md`
   and `src/assets/templates/contoso-brand-guidelines.md`, and embeds the
   source deck's SHA-256 hash in a header comment so drift can be detected.
3. Verify the summary is in sync with the source deck (useful in CI or before
   a release):

   ```powershell
   python scripts/extract_brand_guidelines.py --check
   ```

   This exits non-zero and lists any stale file if the markdown doesn't match
   the current brand deck's hash.
4. Run the targeted tests that guard this contract:

   ```powershell
   python -m pytest tests/test_brand_guidelines_extraction.py tests/test_hosted_agents.py tests/test_pptx_skill.py -q
   ```

5. Re-provision the Prompt agents (`scripts/provision_prompt_agents.py`) so
   the updated 22-slide deck is re-uploaded as their Code Interpreter
   attachment, and redeploy the Hosted case-study agent
   (`azd deploy hosted-case-study-agent`) so it picks up the new embedded
   instructions text.
6. Re-run the local Hosted corpus (`scripts/run_hosted_local_corpus.py`) and
   spot-check rendered output (see the PPTX skill's visual QA guidance) before
   deploying to Azure.

## Why not just let the Hosted agent read the PPTX directly?

Two reasons this was rejected in favor of the markdown extraction:

- **It's technically impossible today.** The sandbox correctly refuses to
  resolve a path outside its root; that's a security feature, not a bug to
  route around.
- **Even with access, raw PPTX is a poor way to deliver guidance to a model.**
  The generator would need to parse OOXML shape trees itself at every run to
  recover text that a one-time extraction already produces as clean markdown.
  Extracting once, at authoring time, is cheaper, deterministic, and
  reviewable in a pull request diff.
