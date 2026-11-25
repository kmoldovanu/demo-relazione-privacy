"""Estrazione del testo dai PDF, in locale con PyMuPDF: nessun servizio esterno."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class Documento:
    percorso: Path
    testo: str
    pagine: int
    impronta: str  # SHA-256 del file: identifica il documento nel registro senza scriverne il contenuto

    @property
    def nome(self) -> str:
        return self.percorso.name


def leggi_pdf(percorso: str | Path) -> Documento:
    percorso = Path(percorso)
    dati = percorso.read_bytes()
    with pymupdf.open(stream=dati, filetype="pdf") as pdf:
        testo = "\n".join(pagina.get_text("text") for pagina in pdf)
        pagine = pdf.page_count
    if not testo.strip():
        # PDF scansionato (solo immagini): servirebbe un OCR locale, ad esempio Tesseract.
        raise ValueError(f"{percorso.name}: nessun testo trovato, probabilmente è una scansione da passare all'OCR.")
    return Documento(percorso, testo, pagine, hashlib.sha256(dati).hexdigest())
