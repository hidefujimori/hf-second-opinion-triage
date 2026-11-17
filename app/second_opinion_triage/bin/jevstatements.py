#!/usr/bin/env python
"""| jevstatements  —  the analyst statements that can be given to a re-triage (built-in and admin-defined).

Output: one row per statement: id, label_en, label_ja, text (the English sentence sent to the decision model),
custom (0 built-in, 1 added by an admin). Used by the triage and Setup pages.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
sys.path.insert(0, HERE)

from splunklib.searchcommands import Configuration, GeneratingCommand, dispatch  # noqa: E402

from jev_triage import conditions  # noqa: E402


@Configuration(distributed=False)
class JevStatementsCommand(GeneratingCommand):
    def generate(self):
        for c in conditions.all_statements(self.service):
            yield {"id": c["id"], "label_en": c.get("label_en", ""), "label_ja": c.get("label_ja", ""),
                   "text": c["text"], "custom": 1 if c.get("custom") else 0}


dispatch(JevStatementsCommand, sys.argv, sys.stdin, sys.stdout, __name__)
