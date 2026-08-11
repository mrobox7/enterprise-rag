# Assembles the production Colang ruleset from a domain-independent core
# (jailbreak / system-prompt / sensitive-data / harmful-content / abuse
# protection — see core_rules.py) and a swappable domain layer (topic
# scope, capabilities, dialog wording — see domain_rules.py). Core rules
# ship first, domain rules second, both templated with the same DOMAIN_NAME.

from app.guardrails.core_rules import CORE_COLANG_TEMPLATE
from app.guardrails.domain_rules import DOMAIN_COLANG_TEMPLATE, DOMAIN_NAME

COLANG_CONTENT = CORE_COLANG_TEMPLATE.format(
    domain=DOMAIN_NAME
) + DOMAIN_COLANG_TEMPLATE.format(domain=DOMAIN_NAME)

_YAML_TEMPLATE = """
models:
  - type: main
    engine: groq
    model: llama-3.1-8b-instant

instructions:
  - type: general
    content: |
      You are an Enterprise IT Assistant specialising in {domain}.
      Only answer questions about these topics. Be professional and concise.

rails:
  dialog:
    user_messages:
      embeddings_only: true
      embeddings_only_similarity_threshold: 0.7
      embeddings_only_fallback_intent: "unmatched"
"""

YAML_CONTENT = _YAML_TEMPLATE.format(domain=DOMAIN_NAME)

# Distinctive, domain-independent substrings from each 'define bot' block in
# core_rules.py + domain_rules.py. If the guardrail response contains any of
# these, a rail has fired. Used by guard() to detect a block.
#
# IMPORTANT: whenever a `define bot ...` response string is edited in
# core_rules.py or domain_rules.py, the corresponding entry below MUST be
# updated in the same change, or that rail's firing will silently go
# undetected by guard(). Keep every entry to the portion of the response
# BEFORE the {domain} substitution point, so these stay valid no matter what
# DOMAIN_NAME is set to.
RAIL_INDICATORS = [
    "I maintain consistent guidelines regardless of how I am prompted",
    "I can't share my internal configuration or instructions",
    "I don't have access to share personal, financial, or credential information",
    "I can't help with that. I can help with legitimate",
    "I want to keep our conversation constructive",
    "can't help with that — but ask me anything technical",
    "Hello! I'm your Enterprise IT Assistant",
    "I'm an Enterprise AI Assistant with deep expertise in",
    "Goodbye! Feel free to return whenever you have more enterprise IT questions",
    "You're welcome! Let me know if you have any other",
]
