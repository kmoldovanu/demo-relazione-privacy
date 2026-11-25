"""Il passaggio all'AI: riceve solo testo già pseudonimizzato e restituisce la bozza della relazione.

La bozza è strutturata (oggetto, stato dei luoghi, criticità, verifiche, conclusione), così il
documento finale si compone in locale con un modello fisso e i dati veri. L'AI non vede mai né i
dati personali né il documento finito.

Due modalità:
- "simulata" (predefinita): nessuna rete, bozza costruita con regole semplici. Serve a mostrare il
  flusso ovunque, anche offline, senza chiavi.
- "api": qualsiasi servizio con API compatibile OpenAI (/v1/chat/completions). Lo stesso codice
  funziona con un modello in locale (Ollama, vLLM: i dati non escono proprio) o con un fornitore
  con server in Europa e contratto sul trattamento dei dati (DPA).
  Si configura con le variabili d'ambiente:
      PRIVACY_AI_URL     es. http://localhost:11434/v1  (Ollama)
      PRIVACY_AI_MODELLO es. llama3.1
      PRIVACY_AI_CHIAVE  se il servizio la richiede
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import Counter

CAMPI = ("oggetto", "stato_luoghi", "criticita", "verifiche", "conclusione")

ISTRUZIONI = (
    "Sei un tecnico di uno studio di accertamenti immobiliari e prepari la bozza di una relazione. "
    "Nel documento ricevuto i dati personali sono sostituiti da segnaposto tra parentesi quadre, ad "
    "esempio [PERSONA_1] o [INDIRIZZO_2]: riportali esattamente come sono e non cercare di indovinarne "
    "il valore. Rispondi SOLO con un oggetto JSON con queste chiavi, in italiano, tono tecnico:\n"
    '  "oggetto": una frase sull\'oggetto dell\'accertamento,\n'
    '  "stato_luoghi": un paragrafo sullo stato dei luoghi descritto nel documento,\n'
    '  "criticita": elenco di stringhe con le possibili difformità o criticità,\n'
    '  "verifiche": elenco di stringhe con le verifiche consigliate,\n'
    '  "conclusione": un paragrafo di conclusione prudente (le verifiche vanno confermate dal tecnico).'
)

# Parole che indicano una possibile difformità, con la frase da usare nella relazione.
SEGNALI = {
    "veranda": "Veranda chiusa: possibile aumento di volume, da verificare con i titoli edilizi.",
    "tettoia": "Tettoia: verificare che sia stata autorizzata.",
    "soppalco": "Soppalco: possibile aumento della superficie utile.",
    "non presente in planimetria": "Stato dei luoghi non conforme alla planimetria catastale.",
    "non risulta": "Elementi non risultanti dalla documentazione disponibile.",
    "cambio di destinazione": "Possibile cambio di destinazione d'uso.",
    "umidità": "Tracce di umidità: da riportare nello stato di conservazione.",
    "difform": "Difformità segnalata nel documento.",
}
DESCRITTIVE = ("composto", "corrisponde", "stato dei luoghi", "presente", "notato", "notano", "realizzat")


def chiedi(testo: str, modalita: str = "simulata") -> dict:
    if modalita == "simulata":
        return _simulata(testo)
    if modalita == "api":
        return _api(testo)
    raise ValueError(f"modalità AI sconosciuta: {modalita}")


def come_testo(bozza: dict) -> str:
    righe = [f"OGGETTO\n{bozza['oggetto']}", f"\nSTATO DEI LUOGHI\n{bozza['stato_luoghi']}", "\nCRITICITÀ"]
    righe += [f"- {c}" for c in bozza["criticita"]] or ["- nessuna"]
    righe.append("\nVERIFICHE CONSIGLIATE")
    righe += [f"- {v}" for v in bozza["verifiche"]]
    righe.append(f"\nCONCLUSIONE\n{bozza['conclusione']}")
    return "\n".join(righe)


def _frasi(testo: str) -> list[str]:
    piatto = re.sub(r"\s+", " ", testo)
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", piatto) if f.strip()]


def _maiuscola(frase: str) -> str:
    return frase[:1].upper() + frase[1:]


def _simulata(testo: str) -> dict:
    basso = testo.lower()
    citazioni = Counter(re.findall(r"\[PERSONA_\d+\]", testo))
    principale = citazioni.most_common(1)[0][0] if citazioni else "la proprietà"  # la persona più citata
    immobile = (re.findall(r"\[IMMOBILE_\d+\]", testo) or ["l'unità immobiliare"])[0]
    indirizzo = (re.findall(r"\[INDIRIZZO_\d+\]", testo) or [""])[0]
    criticita = [descr for parola, descr in SEGNALI.items() if parola in basso]

    descrittive = [
        _maiuscola(f.removeprefix("Stato dei luoghi: "))
        for f in _frasi(testo)
        if any(k in f.lower() for k in DESCRITTIVE + tuple(SEGNALI))
        and not any(k in f.lower() for k in ("contattabile", "nato/a", "[telefono_", "[email_"))
    ]
    richiesta = "effettuato il sopralluogo" not in basso
    oggetto = (
        f"Accertamento sull'immobile {immobile}{' sito in ' + indirizzo if indirizzo else ''}, "
        + ("richiesto in vista della compravendita." if richiesta else "a seguito di sopralluogo.")
    )
    verifiche = ["Confronto dello stato dei luoghi con i titoli edilizi depositati in Comune."]
    if criticita:
        verifiche += [
            "Confronto con la planimetria catastale in atti.",
            "Se le difformità sono confermate: valutare sanatoria e aggiornamento catastale (DOCFA) prima del rogito.",
        ]
    verifiche.append(f"Richiedere a {principale} la documentazione edilizia disponibile.")
    if richiesta:
        verifiche.insert(0, f"Concordare il sopralluogo con {principale}.")
    conclusione = (
        "Sulla base della documentazione esaminata emergono elementi che richiedono approfondimento prima "
        "della compravendita. Le valutazioni sono da confermare a seguito delle verifiche indicate."
        if criticita
        else "Dalla documentazione esaminata non emergono criticità. Le valutazioni sono da confermare a cura del tecnico."
    )
    return {
        "oggetto": oggetto,
        "stato_luoghi": " ".join(descrittive) or "Non descritto nel documento: da rilevare in sopralluogo.",
        "criticita": criticita,
        "verifiche": verifiche,
        "conclusione": conclusione,
    }


def _api(testo: str) -> dict:
    url = os.environ.get("PRIVACY_AI_URL", "http://localhost:11434/v1").rstrip("/")
    modello = os.environ.get("PRIVACY_AI_MODELLO", "llama3.1")
    intestazioni = {"content-type": "application/json"}
    if chiave := os.environ.get("PRIVACY_AI_CHIAVE"):
        intestazioni["authorization"] = f"Bearer {chiave}"
    corpo = {
        "model": modello,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": ISTRUZIONI}, {"role": "user", "content": testo}],
    }
    richiesta = urllib.request.Request(
        f"{url}/chat/completions", data=json.dumps(corpo).encode(), headers=intestazioni, method="POST"
    )
    with urllib.request.urlopen(richiesta, timeout=120) as risposta:
        contenuto = json.load(risposta)["choices"][0]["message"]["content"]
    trovato = re.search(r"\{.*\}", contenuto, re.DOTALL)
    bozza = json.loads(trovato.group(0) if trovato else contenuto)
    return {
        "oggetto": str(bozza.get("oggetto", "")),
        "stato_luoghi": str(bozza.get("stato_luoghi", "")),
        "criticita": [str(c) for c in bozza.get("criticita", [])],
        "verifiche": [str(v) for v in bozza.get("verifiche", [])],
        "conclusione": str(bozza.get("conclusione", "")),
    }
