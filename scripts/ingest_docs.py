"""Index the sample policy documents into the knowledge base.  Usage: python -m scripts.ingest_docs [dir]"""

import re
import sys
from pathlib import Path

from app.core.exceptions import ConflictError
from app.db.session import SessionLocal
from app.schemas.knowledge import DocumentCreate
from app.services.rag.knowledge_service import KnowledgeService


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/knowledge")
    with SessionLocal() as db:
        service = KnowledgeService(db)
        for path in sorted(folder.glob("*.md")) + sorted(folder.glob("*.txt")):
            text = path.read_text(encoding="utf-8")
            heading = re.match(r"#\s+(.+)", text)
            title = heading.group(1).strip() if heading else path.stem.replace("-", " ").title()
            try:
                document = service.ingest(DocumentCreate(title=title, content=text, source_name=path.name))
                print(f"indexed {document.title!r}: {document.chunk_count} chunks")
            except ConflictError:
                print(f"skipped {path.name} (already indexed)")


if __name__ == "__main__":
    main()
