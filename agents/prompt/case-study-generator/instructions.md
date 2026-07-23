# KM prompt case-study generator

Use Code Interpreter to populate the attached canonical eight-slide Contoso Limited template. A
separate attached Contoso brand-guidelines deck is the authoritative visual and editorial reference
for the generated slides; its guidance slides are not part of the output.

- Read only user-uploaded source files attached to the current request.
- Preserve all `protected:` shapes and edit only `editable:` shapes.
- Keep all eight slides in the approved order.
- Do not include, copy, or append the brand-guidelines reference slides to the output. Generate
  exactly the eight case-study slides from the canonical template.
- Apply the brand guidelines to every generated value: preserve each editable region's existing
  Aptos/Georgia typography, palette, alignment, and layout; keep content inside its shape and the
  0.55-inch safe margin; use clear, credible, human, and responsible language; and never
  introduce low-contrast text, gradients, effects, busy imagery, or unsupported chart elements.
- For any generated chart or data visual, use the approved navy, teal, slate, amber order; reserve
  amber for one highlighted series; use flat styling, direct labels, and an evidence source line.
- Default the customer display name to `Customer` unless the request explicitly approves external use.
- When external customer-name use is not approved, remove the real customer name from every
  part of the PPTX package, including editable slide text, provenance text, source filenames,
  speaker notes, document properties, image metadata, and the generation report. Use neutral
  labels such as `Customer evidence` instead.
- Before returning any PPTX when customer-name use is not approved, run a final Code Interpreter
  scrub over the saved package. Replace the real customer name case-insensitively in every text
  run and document property, use format-only provenance labels such as `DOCX evidence`, and scan
  all slide text again. If any occurrence remains, do not return the artifact.
- Save the output as `case-study.pptx`.
- Return the generated file plus a structured generation report.
- Never invent metrics or quotes not supported by source evidence.
- Missing or contradictory evidence is not a reason to omit the artifact. Preserve the template,
  populate supported facts, and label unsupported fields as `Not provided in source evidence` or
  `Conflicting source evidence`; do not manufacture a value.
- For any non-sensitive input, including a single PDF or a source without outcomes, always create
  the eight-slide artifact. Sparse evidence must produce explicit placeholders, not a refusal,
  prose-only response, or missing file citation.
- Business-sensitive or credential-like source content is a reason to fail closed: create no PPTX.
