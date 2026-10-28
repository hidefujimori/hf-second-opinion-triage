[jev]
display_name = <string>
model = <string>
questions_file = <string>
confidence_threshold = <float>
escalation_floor = <float>
rollup_urgency_cap = low|medium|high|critical|<empty>
order_check = <bool>
timeout = <int>
proxy = <url>
parallel = <int 1-8>

[enrichment]
enabled = <bool>
shared_entities = <comma-separated wildcard patterns>
max_facts = <int>

[llm]
provider = anthropic|openai|bedrock|gemini
model = <string>
endpoint = <url>
region = <string>
thinking_level = minimal|<empty>
max_tokens = <int>
timeout = <int>
language = en|ja
proxy = <url>

[es_note]
language = en|ja

[manual]
write_note = <bool>
explain = <bool>

[limits]
jev_auto_daily = <int|empty>
* Findings sent to Jev per day by automatic runs. Empty = no limit.
llm_auto_daily = <int|empty>
* LLM explanations made automatically per day. Empty = no limit, 0 = none.
