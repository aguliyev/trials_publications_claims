"""Instructions for extracting claims from annotated sources."""

CLAIM_PROMPTS = {
    "intervention_worked_for_disease": (
        "Identify only reported positive treatment outcomes where an intervention worked for a disease. "
        "A study objective, hypothesis, ongoing trial, negative result, or mere co-mention is not evidence of efficacy. "
        "Use the NER mentions as context, not proof. Return zero claims if there is no explicit positive result. "
        "For each claim return a verbatim evidence excerpt and the IDs of NER mentions supporting it. "
        "Only use NER IDs provided in this section; do not invent entities or results."
    ),
}

CLAIM_PROMPT_TEMPLATE = '{instruction}\nSection: {section}\nText: {text}\nNER mentions: {mentions}'
