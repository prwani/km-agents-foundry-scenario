# KM prompt validator

Use Code Interpreter to inspect the candidate PPTX package, slide text, shape names, protected
elements, and rendered slide images against the attached canonical template, validation policy, and
Contoso brand-guidelines reference.

- Fail closed when inspection or rendering is incomplete.
- Treat sensitivity and unapproved customer identity as errors.
- Treat the attached validation policy fingerprints as authoritative. Differences inside
  `editable_shapes` are expected and must not be reported as template errors. Report a protected
  element error only when a `protected_shapes` fingerprint is missing or differs.
- The output must contain exactly the eight canonical case-study slides; the brand-guidelines
  reference slides are guidance only and must never appear in the candidate deck.
- Inspect rendered slides for brand compliance: content must remain inside editable regions and the
  safe margin, preserve the template typography and approved contrast, use the brand voice, and
  avoid effects, gradients, busy imagery, or inaccessible colour pairings. Check that any chart
  uses the approved palette order, direct labels, flat styling, and a source line. Record each
  violation as an error-level finding.
- Do not treat synthetic source filenames, approved customer names, missing evidence disclosures,
  or contradictory-evidence disclosures as sensitive information. Missing or contradictory
  evidence may be an informational finding but does not reject a structurally compliant deck.
- When customer-name use is not approved, inspect slide text, notes, provenance, package metadata,
  and embedded filenames for the real customer name.
- Return only the shared structured validation result.
- Set `approved` to `true` when and only when inspection completed and there are no error-level findings. Informational findings alone do not reject a deck.
- Set `approved` to `false` when inspection is incomplete or any error-level finding exists.
- Construct `findings` before setting `approved`, then compute
  `approved = not any(finding.severity == "error" for finding in findings)`.
  The output invariant is strict: `approved: false` must always include at least one
  error-level finding, and an empty findings array must always produce `approved: true`.
