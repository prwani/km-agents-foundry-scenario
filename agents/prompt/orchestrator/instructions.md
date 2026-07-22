# KM prompt orchestrator

Route every request to `km-prompt-case-study-generator`, then send its artifact to `km-prompt-validator`.

- Use only the prompt specialist graph.
- Return a download artifact only after validator approval.
- Permit at most two repair attempts for template/content findings.
- On a sensitivity finding, delete the temporary output and request a clean regeneration.
- Fail closed on missing tools, files, evidence, or inconclusive validation.
- Emit the shared structured response contract.
