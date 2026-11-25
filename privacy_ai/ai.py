"""Il passaggio all'AI. Riceve solo testo già pseudonimizzato.

Due modalità:
- "simulata" (predefinita): nessuna rete, risposta costruita con regole semplici. Serve a
  mostrare il flusso ovunque, anche offline, senza chiavi.
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

ISTRUZIONI = (
    "Sei un assistente per uno studio di accertamenti immobiliari. Ricevi documenti in cui i dati "
    "personali sono stati sostituiti da segnaposto tra parentesi quadre, ad esempio [PERSONA_1] o "
    "[INDIRIZZO_2]. Riporta i segnaposto esattamente come sono, senza tentare di indovinare i valori. "
    "Rispondi in italiano con: 1) sintesi in 3 righe, 2) possibili difformità o criticità, "
    "3) verifiche consigliate."
)

# Parole che in una relazione di sopralluogo indicano una possibile difformità.
SEGNALI = {
    "veranda": "veranda chiusa: possibile aumento di volume da verificare con i titoli edilizi",
    "tettoia": "tettoia: verificare se è stata autorizzata",
    "soppalco": "soppalco: possibile aumento di superficie utile",
    "non presente in planimetria": "stato dei luoghi diverso dalla planimetria catastale",
    "non risulta": "elemento non risultante dai documenti",
    "cambio di destinazione": "possibile cambio di destinazione d'uso",
    "umidità": "segni di umidità: da annotare nello stato di conservazione",
    "difform": "difformità dichiarata nel testo",
}


def chiedi(testo: str, modalita: str = "simulata") -> str:
    if modalita == "simulata":
        return _simulata(testo)
    if modalita == "api":
        return _api(testo)
    raise ValueError(f"modalità AI sconosciuta: {modalita}")


def _simulata(testo: str) -> str:
    citazioni = Counter(re.findall(r"\[PERSONA_\d+\]", testo))
    persone = sorted(citazioni)
    principale = citazioni.most_common(1)[0][0] if citazioni else "la proprietà"  # la persona più citata
    luoghi = sorted(set(re.findall(r"\[(?:INDIRIZZO|IMMOBILE)_\d+\]", testo)))
    basso = testo.lower()
    criticita = [descr for parola, descr in SEGNALI.items() if parola in basso]

    righe = ["1) Sintesi"]
    righe.append(
        f"   Documento relativo a {', '.join(luoghi) or 'un immobile'}"
        "."
    )
    if persone:
        righe.append(f"   Persone citate: {', '.join(persone)}.")
    if "effettuato il sopralluogo" in basso:
        righe.append("   Contiene l'esito di un sopralluogo con osservazioni sullo stato dei luoghi.")
    elif "chiediamo" in basso or "richiesta" in basso:
        righe.append("   È una richiesta di verifica prima di una compravendita o di una pratica.")
    righe.append("2) Possibili criticità")
    righe += [f"   - {c}" for c in criticita] or ["   - nessuna segnalata nel testo"]
    righe.append("3) Verifiche consigliate")
    if criticita:
        righe.append("   - confronto con i titoli edilizi in Comune e con la planimetria catastale")
        righe.append("   - se confermate, valutare l'aggiornamento catastale (DOCFA)")
    righe.append(f"   - contattare {principale} per la documentazione mancante")
    return "\n".join(righe)


def _api(testo: str) -> str:
    url = os.environ.get("PRIVACY_AI_URL", "http://localhost:11434/v1").rstrip("/")
    modello = os.environ.get("PRIVACY_AI_MODELLO", "llama3.1")
    intestazioni = {"content-type": "application/json"}
    if chiave := os.environ.get("PRIVACY_AI_CHIAVE"):
        intestazioni["authorization"] = f"Bearer {chiave}"
    corpo = {
        "model": modello,
        "temperature": 0.2,
        "messages": [{"role": "system", "content": ISTRUZIONI}, {"role": "user", "content": testo}],
    }
    richiesta = urllib.request.Request(
        f"{url}/chat/completions", data=json.dumps(corpo).encode(), headers=intestazioni, method="POST"
    )
    with urllib.request.urlopen(richiesta, timeout=120) as risposta:
        return json.load(risposta)["choices"][0]["message"]["content"]
