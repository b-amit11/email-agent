"""The knowledge base: the facts the agent is allowed to answer from.

Each fact sheet is a plain text file in the knowledge/ folder.
"""

from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def load_knowledge() -> str:
    """Read every fact sheet and join them into one block of text."""
    sheets = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        sheets.append(f'<document name="{path.stem}">\n{text}\n</document>')
    return "\n\n".join(sheets)
