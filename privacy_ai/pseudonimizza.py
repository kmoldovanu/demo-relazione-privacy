"""Pseudonimizzazione reversibile: i dati personali diventano segnaposto prima di lasciare l'azienda.

Esempio:
    "Sig.ra Elena Giraudo, C.F. GRDLNE78C54H727N"  ->  "Sig.ra [PERSONA_1], C.F. [CF_1]"

La tabella segnaposto -> valore vero (il "caveau") resta solo in memoria, sul computer
dell'azienda. Fuori esce soltanto il testo con i segnaposto; quando torna la risposta
dell'AI, i valori veri si rimettono qui, in locale.

Come si trovano i dati:
- con espressioni regolari, per i dati con un formato riconoscibile (codice fiscale, IBAN,
  email, telefono, partita IVA, indirizzi, identificativi catastali, dati di nascita);
- con le regole del dominio, per i nomi: gli intestatari delle visure ("Intestato 1: COGNOME
  NOME nato a ...") e i titoli ("Sig.ra", "Geom.", "Dott.", ...). Un nome imparato da un
  documento viene sostituito in tutti gli altri, anche se lì compare scritto in modo diverso
  o solo con il cognome.

Prima dell'invio, `verifica_uscita` controlla che nel testo non sia rimasto nulla di
riconoscibile: se trova qualcosa blocca l'invio invece di fidarsi.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# Ordine importante: l'email va tolta prima dei nomi ("elena.giraudo@..." contiene il nome).
PATTERN: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("IBAN", re.compile(r"\bIT\d{2}[A-Z]\d{10}[0-9A-Z]{12}\b", re.IGNORECASE)),
    ("CF", re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPR-T]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)),
    ("PIVA", re.compile(r"(?i:\b(?:P\.?\s?IVA|partita\s+iva)\s*:?\s*)(\d{11})\b")),
    ("TELEFONO", re.compile(r"(?<![\d/])(?:\+39\s?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{3,4}(?![\d/])")),
    (
        "IMMOBILE",
        re.compile(
            r"\bFoglio\s+\d+\s*,?\s*(?:Particella|Mappale)\s+\d+(?:\s*,?\s*(?:Subalterno|Sub\.?)\s+\d+)?",
            re.IGNORECASE,
        ),
    ),
    (
        "INDIRIZZO",
        re.compile(
            r"\b(?:Via|Viale|Corso|Piazza|Piazzale|Strada|Vicolo|Largo|Borgata|Frazione)"
            r"\s+(?:[A-Za-zÀ-ÿ']+\s+){0,4}?(?:n\.\s*)?\d+[A-Za-z]?(?:/[A-Za-z0-9]+)?",
            re.IGNORECASE,
        ),
    ),
]

# "nata a SALUZZO il 14/03/1978": luogo e data di nascita, insieme, identificano una persona.
NASCITA = re.compile(
    r"\bnat[oa]\s+a\s+(?P<luogo>[A-Za-zÀ-ÿ' ]+?)\s*(?:\([A-Z]{2}\)\s*)?\s+il\s+(?P<data>\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)

# Visura: "Intestato 1: GIRAUDO ELENA nata a ..." (cognome e nome, in maiuscolo).
INTESTATARIO = re.compile(r"\bIntestat[oa]\s*\d*\s*:\s*(?P<nome>[A-ZÀ-Ý' ]+?)\s+nat[oa]\b")

# Testo libero: "Sig.ra Elena Giraudo", "Geom. Paolo Martini".
TITOLO = re.compile(
    r"\b(?:Sig\.ra|Sig\.|Signora|Signor|Dott\.ssa|Dott\.|Geom\.|Ing\.|Arch\.|Avv\.|Notaio)\s+"
    r"(?P<nome>[A-ZÀ-Ý][a-zà-ÿ']+(?:\s+[A-ZÀ-Ý][a-zà-ÿ']+){0,2})"
)

SEGNAPOSTO = re.compile(r"\[([A-Z_]+_\d+)\]")

# Parole che possono seguire un titolo senza essere un nome ("Sig.ra Proprietaria", "Geom. Incaricato").
NON_NOMI = {"proprietario", "proprietaria", "incaricato", "incaricata", "sottoscritto", "sottoscritta"}


def _chiave(valore: str) -> str:
    """Forma normalizzata: lo stesso dato scritto in modi diversi prende lo stesso segnaposto."""
    return re.sub(r"[\s.-]+", " ", valore).strip().casefold()


@dataclass
class Persona:
    nome: str  # forma da rimettere nella risposta, es. "Giraudo Elena"
    varianti: set[str] = field(default_factory=set)  # forme da cercare nel testo


@dataclass
class Pseudonimizzatore:
    """Tiene il caveau di una sessione di lavoro. Non scrive niente su disco."""

    caveau: dict[str, str] = field(default_factory=dict)  # "[CF_1]" -> "GRDLNE78C54H727N"
    _per_valore: dict[tuple[str, str], str] = field(default_factory=dict)
    _contatori: Counter[str] = field(default_factory=Counter)
    persone: list[Persona] = field(default_factory=list)
    luoghi_nascita: set[str] = field(default_factory=set)

    # --- 1. imparare chi sono le persone, da tutti i documenti --------------------------------

    def impara(self, testo: str) -> None:
        for m in INTESTATARIO.finditer(testo):
            self._aggiungi_persona(m.group("nome"))
        for m in TITOLO.finditer(testo):
            if m.group("nome").split()[0].casefold() not in NON_NOMI:
                self._aggiungi_persona(m.group("nome"))
        for m in NASCITA.finditer(testo):
            self.luoghi_nascita.add(m.group("luogo").strip())

    def _aggiungi_persona(self, grezzo: str) -> None:
        parti = [p for p in re.split(r"\s+", grezzo.strip()) if p]
        if not parti:
            return
        varianti = {" ".join(parti), " ".join(reversed(parti))}
        varianti |= {p for p in parti if len(p) >= 3}  # anche solo cognome o solo nome
        chiavi = {_chiave(v) for v in varianti}
        for persona in self.persone:  # stessa persona vista in un altro documento
            if chiavi & {_chiave(v) for v in persona.varianti if " " in v} or (
                len(parti) == 1 and _chiave(parti[0]) in {_chiave(v) for v in persona.varianti}
            ):
                persona.varianti |= varianti
                return
        self.persone.append(Persona(nome=" ".join(p.capitalize() for p in parti), varianti=varianti))

    # --- 2. sostituire ------------------------------------------------------------------------

    def _segnaposto(self, categoria: str, valore: str) -> str:
        chiave = (categoria, _chiave(valore))
        if chiave not in self._per_valore:
            self._contatori[categoria] += 1
            segnaposto = f"[{categoria}_{self._contatori[categoria]}]"
            self._per_valore[chiave] = segnaposto
            self.caveau[segnaposto] = valore
        return self._per_valore[chiave]

    def applica(self, testo: str) -> str:
        for categoria, pattern in PATTERN:
            if pattern.groups:  # il pattern ha un'etichetta da lasciare (es. "P.IVA"): si sostituisce solo il numero
                testo = pattern.sub(
                    lambda m, c=categoria: m.group(0).replace(m.group(1), self._segnaposto(c, m.group(1))), testo
                )
            else:
                testo = pattern.sub(lambda m, c=categoria: self._segnaposto(c, m.group(0)), testo)

        testo = NASCITA.sub(
            lambda m: f"nato/a a {self._segnaposto('LUOGO_NASCITA', m.group('luogo').strip())}"
            f" il {self._segnaposto('DATA_NASCITA', m.group('data'))}",
            testo,
        )
        for luogo in self.luoghi_nascita:  # il comune di nascita, se ricompare altrove
            testo = re.sub(
                rf"\b{re.escape(luogo)}\b",
                lambda m, v=luogo: self._segnaposto("LUOGO_NASCITA", v),
                testo,
                flags=re.IGNORECASE,
            )

        # I nomi per ultimi, dalle forme più lunghe ("Elena Giraudo") alle più corte ("Giraudo").
        forme = sorted(
            ((v, persona) for persona in self.persone for v in persona.varianti),
            key=lambda x: len(x[0]),
            reverse=True,
        )
        for variante, persona in forme:
            testo = re.sub(
                rf"(?<![\w\[]){re.escape(variante).replace(r'\ ', r'\s+')}(?![\w\]])",
                lambda m, p=persona: self._segnaposto("PERSONA", p.nome),
                testo,
                flags=re.IGNORECASE,
            )
        return testo

    # --- 3. controllare e rimettere -----------------------------------------------------------

    def verifica_uscita(self, testo: str) -> list[str]:
        """Cosa di riconoscibile è rimasto nel testo da inviare. Lista vuota = si può inviare."""
        problemi = [f"{categoria}: {m.group(0)}" for categoria, p in PATTERN for m in p.finditer(testo)]
        problemi += [f"NASCITA: {m.group(0)}" for m in NASCITA.finditer(testo)]
        for valore in self.caveau.values():
            if len(valore) >= 3 and re.search(rf"\b{re.escape(valore)}\b", testo, re.IGNORECASE):
                problemi.append(f"valore noto ancora presente: {valore}")
        return problemi

    def reidentifica(self, dato):
        """Rimette i valori veri in una stringa, o in tutte le stringhe di una lista o di un dizionario."""
        if isinstance(dato, str):
            return SEGNAPOSTO.sub(lambda m: self.caveau.get(f"[{m.group(1)}]", m.group(0)), dato)
        if isinstance(dato, list):
            return [self.reidentifica(x) for x in dato]
        if isinstance(dato, dict):
            return {k: self.reidentifica(v) for k, v in dato.items()}
        return dato

    def valori(self, categoria: str) -> list[str]:
        """I valori veri di una categoria, es. tutti gli identificativi catastali trovati."""
        return [v for k, v in self.caveau.items() if k.startswith(f"[{categoria}_")]

    def riepilogo(self) -> dict[str, int]:
        return dict(self._contatori)

    def dimentica(self) -> None:
        """Fine lavoro: il caveau si svuota e i valori veri non restano in memoria."""
        self.caveau.clear()
        self._per_valore.clear()
