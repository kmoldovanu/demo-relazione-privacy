"""Composizione della relazione finale in Word (.docx), in locale.

Unisce due fonti:
- i dati certi letti dal parser (intestatari e immobili della visura), che non passano dall'AI;
- la bozza scritta dall'AI (stato dei luoghi, criticità, verifiche), già con i dati veri rimessi.

Il risultato è una BOZZA modificabile: il tecnico la rilegge, la corregge e la firma.
"""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .flusso import Esito
from .pseudonimizza import Pseudonimizzatore

GRIGIO = RGBColor(0x6B, 0x6B, 0x6B)


def _tabella(doc, intestazioni: list[str], righe: list[list[str]]) -> None:
    tabella = doc.add_table(rows=1, cols=len(intestazioni))
    tabella.style = "Light Grid Accent 1"
    for cella, testo in zip(tabella.rows[0].cells, intestazioni):
        cella.text = testo
        cella.paragraphs[0].runs[0].bold = True
    for riga in righe:
        for cella, testo in zip(tabella.add_row().cells, riga):
            cella.text = testo
    doc.add_paragraph()


def _indirizzo(testo: str) -> str:
    """"VIA DEI GLICINI n. 12 piano 2" -> "Via dei Glicini n. 12 piano 2"."""
    minuscole = {"di", "dei", "del", "della", "delle", "degli", "da", "n.", "piano", "int.", "scala"}
    return " ".join(p.lower() if p.lower() in minuscole and i else p.capitalize() for i, p in enumerate(testo.split()))


def _nota(doc, testo: str) -> None:
    run = doc.add_paragraph().add_run(testo)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = GRIGIO


def genera_relazione(esiti: list[Esito], p: Pseudonimizzatore, pratica: str = "2026/418") -> bytes:
    visura = next((e.visura for e in esiti if e.visura), None)
    bozze = [e.bozza_finale for e in esiti if e.bozza_finale]

    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    titolo = doc.add_heading("RELAZIONE DI ACCERTAMENTO IMMOBILIARE", level=0)
    titolo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sotto = doc.add_paragraph(f"Pratica {pratica} · {date.today():%d/%m/%Y}")
    sotto.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _nota(doc, "Bozza generata automaticamente da documenti con dati inventati: da verificare e firmare a cura del tecnico.")

    doc.add_heading("1. Oggetto", level=1)
    doc.add_paragraph(" ".join(b["oggetto"] for b in bozze) or "Accertamento sull'unità immobiliare indicata.")

    doc.add_heading("2. Dati catastali", level=1)
    if visura and visura.immobili:
        doc.add_paragraph(f"Comune di {visura.comune.title()} (codice {visura.codice_comune}), Catasto Fabbricati.")
        _tabella(
            doc,
            ["Foglio", "Part.", "Sub.", "Cat.", "Classe", "Consistenza", "Rendita €", "Indirizzo"],
            [
                [i.foglio, i.particella, i.subalterno, i.categoria, i.classe, i.consistenza,
                 f"{i.rendita_euro:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), _indirizzo(i.indirizzo)]
                for i in visura.immobili
            ],
        )
        _nota(doc, "Fonte: visura catastale, letta con un parser in locale (nessun invio all'AI).")
    else:
        for identificativo in p.valori("IMMOBILE") or ["non indicato"]:
            doc.add_paragraph(identificativo, style="List Bullet")
        _nota(doc, "Visura non fornita: dati catastali da verificare con visura aggiornata.")

    doc.add_heading("3. Intestatari", level=1)
    if visura and visura.intestatari:
        _tabella(
            doc,
            ["Nominativo", "Codice fiscale", "Nascita", "Diritto"],
            [
                [i.nome.title(), i.codice_fiscale + ("" if i.codice_fiscale_valido else " (!)"),
                 f"{i.luogo_nascita.title()}, {i.data_nascita}", i.diritto]
                for i in visura.intestatari
            ],
        )
    else:
        doc.add_paragraph("Da visura non fornita. Persone citate nei documenti: " + (", ".join(p.valori("PERSONA")) or "nessuna") + ".")

    doc.add_heading("4. Stato dei luoghi", level=1)
    for b in bozze:
        doc.add_paragraph(b["stato_luoghi"])

    doc.add_heading("5. Criticità rilevate", level=1)
    criticita = list(dict.fromkeys(c for b in bozze for c in b["criticita"]))
    for c in criticita or ["Nessuna criticità emersa dalla documentazione esaminata."]:
        doc.add_paragraph(c, style="List Bullet")

    doc.add_heading("6. Verifiche consigliate", level=1)
    for v in dict.fromkeys(v for b in bozze for v in b["verifiche"]):
        doc.add_paragraph(v, style="List Bullet")

    doc.add_heading("7. Conclusioni", level=1)
    for b in bozze:
        doc.add_paragraph(b["conclusione"])

    doc.add_paragraph()
    firma = doc.add_paragraph("Il tecnico incaricato\n\n______________________________")
    firma.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
