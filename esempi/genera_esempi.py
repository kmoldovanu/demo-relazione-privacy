"""Crea i PDF di esempio. Tutti i dati sono INVENTATI: persone, codici fiscali, contatti e IBAN.

    python esempi/genera_esempi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from privacy_ai.visura import carattere_controllo  # noqa: E402

CARTELLA = Path(__file__).resolve().parent


def cf(primi15: str) -> str:
    return primi15 + carattere_controllo(primi15)


CF_GIRAUDO = cf("GRDLNE78C54H727")  # Giraudo Elena, F, 14/03/1978, Saluzzo
CF_BERTOLA = cf("BRTLCU75P02D742")  # Bertola Luca, M, 02/09/1975, Fossano

VISURA = f"""VISURA CATASTALE PER SOGGETTO - ESEMPIO CON DATI INVENTATI
Data: 12/11/2026   Catasto Fabbricati
Comune di CUNEO (D205) - Provincia di CUNEO

DATI DEGLI INTESTATARI
Intestato 1: GIRAUDO ELENA nata a SALUZZO il 14/03/1978  C.F. {CF_GIRAUDO}
Diritto: Proprieta' per 1/2
Intestato 2: BERTOLA LUCA nato a FOSSANO il 02/09/1975  C.F. {CF_BERTOLA}
Diritto: Proprieta' per 1/2

IMMOBILE 1
Foglio 87 Particella 1234 Subalterno 5
Categoria A/2 Classe 3 Consistenza 6 vani Rendita Euro 588,76
Indirizzo: VIA DEI GLICINI n. 12 piano 2

IMMOBILE 2
Foglio 87 Particella 1234 Subalterno 18
Categoria C/6 Classe 2 Consistenza 15 m2 Rendita Euro 41,83
Indirizzo: VIA DEI GLICINI n. 12 piano S1
"""

RELAZIONE = f"""RELAZIONE DI SOPRALLUOGO - ESEMPIO CON DATI INVENTATI

Pratica 2026/418 - Accertamento per compravendita

In data 10/11/2026 il sottoscritto Geom. Paolo Martini ha effettuato il sopralluogo presso l'immobile sito in Via dei Glicini 12, Cuneo, identificato al Foglio 87 Particella 1234 Subalterno 5, di proprietà della Sig.ra Elena Giraudo (C.F. {CF_GIRAUDO}) e del Sig. Luca Bertola.

Era presente la Sig.ra Giraudo, contattabile al 333 812 4471 o all'indirizzo elena.giraudo@esempio.it, che ha consentito l'accesso a tutti i locali.

Stato dei luoghi: l'appartamento al piano secondo è composto da ingresso, soggiorno, cucina, due camere e bagno. Sul balcone lato cortile è presente una veranda chiusa con serramenti in alluminio, non presente in planimetria. Nel bagno si notano tracce di umidità sul soffitto. L'autorimessa al piano interrato corrisponde alla planimetria.

La Sig.ra Giraudo riferisce che la veranda è stata realizzata intorno al 2015 e che non ricorda se sia stata presentata una pratica edilizia. Il Sig. Bertola, nato a Fossano il 02/09/1975, non era presente.

Le spese della pratica saranno saldate con bonifico dall'IBAN IT60X0542811101000000123456 intestato ai proprietari.

Cuneo, 11/11/2026
Geom. Paolo Martini
"""


def scrivi_pdf(nome: str, testo: str) -> Path:
    percorso = CARTELLA / nome
    pdf = pymupdf.open()
    pagina = pdf.new_page(width=595, height=842)  # A4
    pagina.insert_textbox(pymupdf.Rect(56, 56, 539, 800), testo, fontname="helv", fontsize=10.5, lineheight=1.35)
    pdf.set_metadata({"title": nome, "author": "Esempio - dati inventati"})
    pdf.save(percorso, garbage=4, deflate=True)
    return percorso


if __name__ == "__main__":
    for nome, testo in (("visura.pdf", VISURA), ("relazione.pdf", RELAZIONE)):
        print("creato", scrivi_pdf(nome, testo))
