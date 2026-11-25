"""Lettura delle visure catastali senza AI.

Le visure hanno un formato fisso: le stesse etichette, nello stesso ordine. Per questi documenti
un parser classico è più affidabile, più veloce e gratuito, e soprattutto non manda niente a
nessuno. L'AI serve solo per i testi davvero liberi (relazioni, atti, corrispondenza).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

INTESTATO = re.compile(
    r"Intestat[oa]\s*\d*\s*:\s*(?P<nome>[A-ZÀ-Ý' ]+?)\s+nat[oa]\s+a\s+(?P<luogo>[A-ZÀ-Ý' ]+?)\s+il\s+"
    r"(?P<data>\d{2}/\d{2}/\d{4}).*?C\.F\.\s*(?P<cf>[A-Z0-9]{16})"
    r"(?:\s+Diritto:\s*(?P<diritto>[^\n]+))?",
    re.DOTALL,
)
IMMOBILE = re.compile(
    r"Foglio\s+(?P<foglio>\d+)\s+Particella\s+(?P<particella>\d+)\s+Subalterno\s+(?P<sub>\d+)\s+"
    r"Categoria\s+(?P<categoria>[A-Z]/\d+)\s+Classe\s+(?P<classe>\w+)\s+Consistenza\s+(?P<consistenza>[^\n]+?)\s+"
    r"Rendita\s+Euro\s+(?P<rendita>[\d.,]+)\s+Indirizzo:\s*(?P<indirizzo>[^\n]+)"
)
COMUNE = re.compile(r"Comune di\s+(?P<comune>[A-ZÀ-Ý' ]+?)\s*\((?P<codice>[A-Z]\d{3})\)")


@dataclass
class Intestatario:
    nome: str
    luogo_nascita: str
    data_nascita: str
    codice_fiscale: str
    codice_fiscale_valido: bool
    diritto: str


@dataclass
class Immobile:
    foglio: str
    particella: str
    subalterno: str
    categoria: str
    classe: str
    consistenza: str
    rendita_euro: float
    indirizzo: str


@dataclass
class Visura:
    comune: str
    codice_comune: str
    intestatari: list[Intestatario] = field(default_factory=list)
    immobili: list[Immobile] = field(default_factory=list)

    def come_dict(self) -> dict:
        return asdict(self)


def sembra_visura(testo: str) -> bool:
    return "VISURA" in testo.upper() and bool(IMMOBILE.search(_compatta(testo)))


def _compatta(testo: str) -> str:
    # PyMuPDF può spezzare le righe in punti diversi: si uniscono gli spazi, si tengono gli a capo
    return re.sub(r"[ \t]+", " ", testo)


def leggi_visura(testo: str) -> Visura:
    testo = _compatta(testo)
    comune = COMUNE.search(testo)
    visura = Visura(comune.group("comune") if comune else "", comune.group("codice") if comune else "")
    for m in INTESTATO.finditer(testo):
        visura.intestatari.append(
            Intestatario(
                nome=m.group("nome").strip(),
                luogo_nascita=m.group("luogo").strip(),
                data_nascita=m.group("data"),
                codice_fiscale=m.group("cf"),
                codice_fiscale_valido=cf_valido(m.group("cf")),
                diritto=(m.group("diritto") or "").strip(),
            )
        )
    for m in IMMOBILE.finditer(testo):
        visura.immobili.append(
            Immobile(
                foglio=m.group("foglio"),
                particella=m.group("particella"),
                subalterno=m.group("sub"),
                categoria=m.group("categoria"),
                classe=m.group("classe"),
                consistenza=m.group("consistenza").strip(),
                rendita_euro=float(m.group("rendita").replace(".", "").replace(",", ".")),
                indirizzo=m.group("indirizzo").strip(),
            )
        )
    return visura


# --- controllo del carattere finale del codice fiscale (algoritmo ufficiale) -------------------

_DISPARI = dict(
    zip(
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 1, 0, 5, 7, 9, 13, 15, 17, 19, 21,
         2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23],
    )
)


def carattere_controllo(primi15: str) -> str:
    totale = 0
    for i, c in enumerate(primi15.upper()):
        if i % 2 == 0:  # posizioni dispari contando da 1
            totale += _DISPARI[c]
        else:
            totale += int(c) if c.isdigit() else ord(c) - ord("A")
    return chr(ord("A") + totale % 26)


def cf_valido(cf: str) -> bool:
    cf = cf.upper()
    return len(cf) == 16 and cf.isalnum() and carattere_controllo(cf[:15]) == cf[15]
