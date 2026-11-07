"""НОУС · runtime-harness MVA-H v0.1 (ADR-0014): receipts + governor + tools + loop.

LLM не входит в TCB: гейт считает код, доказательства — журнал и мир,
нарратив модели не доверяется. Промпт задаёт протокол; harness обеспечивает
его исполнение.

Публичный API: ReceiptLog, Governor, ToolBox, Auditor, run_plan, make_report,
to_evidence_entry (маппинг на schemas/evidence-entry.schema.json).
"""
from .receipts import GENESIS, ReceiptLog, canonical, iso_ts, sha, to_evidence_entry
from .governor import ALLOW, ASK, DENY, Governor
from .loop import Auditor, make_report, run_plan
from .tools import ToolBox

__version__ = "0.1.0"

__all__ = [
    "ALLOW", "ASK", "DENY", "GENESIS",
    "Auditor", "Governor", "ReceiptLog", "ToolBox",
    "canonical", "iso_ts", "make_report", "run_plan", "sha", "to_evidence_entry",
    "__version__",
]
