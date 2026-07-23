# Synthetic paired evaluation

Run the versioned synthetic corpus three times through both isolated stacks after the
tenant configuration and Hosted session transfer adapter are available. Do not upload
production content or generated customer decks into this workflow.

Each JSONL result record must include the following metadata only:

```json
{
  "case_id": "case-01-clean-docx",
  "implementation": "prompt",
  "repetition": 1,
  "status": "approved",
  "artifact_delivered": true,
  "valid_pptx": true,
  "template_compliant": true,
  "sensitive_information_revealed": false,
  "customer_name_compliant": true,
  "validation_conclusive": true,
  "temporary_artifacts_cleaned": true,
  "observed_customer_display_name": "Customer",
  "uncertainty_finding_present": false,
  "latency_ms": 18420,
  "estimated_cost_usd": 0.03,
  "human_correction_minutes": 0,
  "repair_attempts": 0,
  "content_quality_score": 91,
  "failure_categories": []
}
```

`content_quality_score` can be `null` for a run without a deliverable. Include only
category labels, never source content, customer filenames, URLs, prompts, tokens, or
raw Foundry identifiers.

Create the report:

```powershell
python .\scripts\report_evaluation.py `
  --results .\evaluation\results\synthetic-v1.jsonl `
  --output .\evaluation\reports\synthetic-v1.json
```

The runner rejects missing, duplicate, or unexpected case/implementation/repetition
records, so a valid input has exactly 72 entries. It reports mean, median, p95, and
sample variance for latency, costs, repair attempts, and content scores, plus cost and
human-correction minutes per successful deck.

A stack is eligible for a weighted score only if all runs pass hard safety and template
gates: no sensitive disclosure, customer-name policy compliance, template compliance,
conclusive validation, temporary-artifact cleanup, valid delivered PPTX files, and the
required fail-closed behavior. Eligible stacks are weighted by content quality (40%),
reliability (25%), latency (15%), cost (10%), and human correction effort (10%). Both
stacks remain available in the portal regardless of the recommendation.
