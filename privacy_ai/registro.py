"""Registro delle elaborazioni (accountability, art. 5.2 e 30 GDPR).

Ogni riga dice cosa è stato elaborato, quando, quante sostituzioni sono state fatte e dove è
stato inviato il testo. Il registro non contiene dati personali: il documento è identificato
dalla sua impronta SHA-256, non dal contenuto.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def annota(percorso: Path, **voce: object) -> dict:
    voce = {"quando": datetime.now(timezone.utc).isoformat(timespec="seconds"), **voce}
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("a", encoding="utf-8") as f:
        f.write(json.dumps(voce, ensure_ascii=False) + "\n")
    return voce
