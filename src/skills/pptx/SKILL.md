---
name: contoso-case-study-pptx
description: Generate a Contoso Limited case-study deck from the approved template and structured content.
---

# Contoso case-study PowerPoint skill

Use this skill only for case-study PPTX generation.

## Inputs

- Approved template at `/data/input/template.pptx`.
- Structured content JSON at `/data/input/case-study.json`.
- Template policy at `/data/input/template-policy.json`.

## Required behavior

1. Load the approved template; never create a replacement presentation.
2. Edit only shapes whose names begin with `editable:`.
3. Preserve every `protected:` shape, slide order, layout, color, font, logo, footer, and confidentiality marker.
4. Default the customer display name to `Customer` unless `customer_name_approved_for_external_use` is true.
5. Do not copy raw source-document text into the deck. Use only evidence represented in the structured content contract.
6. Save the deck to `/data/output/case-study.pptx`.
7. Save a generation report to `/data/output/generation-report.json`.
8. Fail explicitly if the template, policy, or required content is missing.

The Python implementation lives in `km_agents.pptx_skill` and is intentionally swappable.
