"""Il flusso completo, usato sia dalla riga di comando sia dall'interfaccia web.

    PDF ──► testo (locale) ──► visura? ── sì ──► dati strutturati, nessuna AI
                                  │
                                  no
                                  ▼
            pseudonimizzazione (locale) ──► controllo uscita ──► AI ──► reidentificazione (locale)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import ai, registro
from .estrazione import Documento
from .pseudonimizza import Pseudonimizzatore
from .visura import Visura, leggi_visura, sembra_visura


class UscitaBloccata(Exception):
    """Il controllo ha trovato dati personali nel testo da inviare: niente parte."""

    def __init__(self, problemi: list[str]):
        super().__init__("; ".join(problemi))
        self.problemi = problemi


@dataclass
class Esito:
    documento: Documento
    visura: Visura | None = None
    testo_inviato: str | None = None
    risposta_ai: str | None = None
    risposta_finale: str | None = None
    sostituzioni: dict[str, int] = field(default_factory=dict)


def elabora(
    documenti: list[Documento],
    modalita_ai: str = "simulata",
    ai_anche_su_visure: bool = False,
    file_registro: Path | None = Path("registro/elaborazioni.jsonl"),
) -> tuple[list[Esito], Pseudonimizzatore]:
    p = Pseudonimizzatore()
    for doc in documenti:  # prima si impara da tutti: un nome letto in una visura si ritrova nella relazione
        p.impara(doc.testo)

    esiti = []
    for doc in documenti:
        esito = Esito(doc)
        if sembra_visura(doc.testo):
            esito.visura = leggi_visura(doc.testo)
            if not ai_anche_su_visure:
                _annota(file_registro, doc, "parser locale", 0, {})
                esiti.append(esito)
                continue

        prima = p.riepilogo()
        esito.testo_inviato = p.applica(doc.testo)
        dopo = p.riepilogo()
        esito.sostituzioni = {k: v - prima.get(k, 0) for k, v in dopo.items() if v - prima.get(k, 0)}

        if problemi := p.verifica_uscita(esito.testo_inviato):
            _annota(file_registro, doc, "BLOCCATO", 0, esito.sostituzioni)
            raise UscitaBloccata(problemi)

        esito.risposta_ai = ai.chiedi(esito.testo_inviato, modalita_ai)
        esito.risposta_finale = p.reidentifica(esito.risposta_ai)
        _annota(file_registro, doc, f"AI {modalita_ai}", len(esito.testo_inviato), esito.sostituzioni)
        esiti.append(esito)
    return esiti, p


def _annota(file: Path | None, doc: Documento, destinazione: str, caratteri: int, sostituzioni: dict) -> None:
    if file is not None:
        registro.annota(
            file,
            documento_sha256=doc.impronta,
            pagine=doc.pagine,
            destinazione=destinazione,
            caratteri_inviati=caratteri,
            segnaposto_per_tipo=sostituzioni,
        )
