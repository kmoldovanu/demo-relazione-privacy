"""Interfaccia web della demo: streamlit run app.py"""

from __future__ import annotations

import html
import json
import re
import tempfile
from pathlib import Path

import streamlit as st

from privacy_ai.ai import come_testo
from privacy_ai.documento import genera_relazione
from privacy_ai.estrazione import Documento, leggi_pdf
from privacy_ai.flusso import UscitaBloccata, elabora
from privacy_ai.pseudonimizza import SEGNAPOSTO

ESEMPI = Path(__file__).parent / "esempi"

st.set_page_config(page_title="Documenti e AI, senza esporre dati personali", page_icon="🔒", layout="wide")
st.markdown(
    """<style>
    .testo{white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:.82rem;line-height:1.55;
           padding:1rem;border-radius:.6rem;border:1px solid rgba(128,128,128,.3);max-height:30rem;overflow:auto}
    mark.vero{background:#fde2e1;color:#8a1c14;padding:0 .15rem;border-radius:.2rem}
    mark.finto{background:#dcf2e3;color:#14532d;padding:0 .15rem;border-radius:.2rem;font-weight:600}
    </style>""",
    unsafe_allow_html=True,
)


def evidenzia(testo: str, valori: list[str] | None = None) -> str:
    """Rosso: dati personali veri. Verde: segnaposto."""
    sicuro = html.escape(testo)
    if valori:
        forme = sorted({html.escape(v) for v in valori if len(v) >= 3}, key=len, reverse=True)
        if forme:
            schema = re.compile("|".join(re.escape(f).replace(r"\ ", r"\s+") for f in forme), re.IGNORECASE)
            sicuro = schema.sub(lambda m: f'<mark class="vero">{m.group(0)}</mark>', sicuro)
    sicuro = SEGNAPOSTO.sub(lambda m: f'<mark class="finto">{m.group(0)}</mark>', sicuro)
    return f'<div class="testo">{sicuro}</div>'


st.title("🔒 Documenti immobiliari e AI, senza esporre dati personali")
st.caption(
    "Demo con dati inventati. Il testo si estrae in locale; nomi, codici fiscali, indirizzi e contatti "
    "diventano segnaposto prima di arrivare all'AI e tornano veri solo alla fine, in locale. "
    "Le visure, che hanno un formato fisso, si leggono senza AI."
)

with st.sidebar:
    st.header("Documenti")
    caricati = st.file_uploader("Carica uno o più PDF", type="pdf", accept_multiple_files=True)
    if not caricati:
        st.info("Nessun file caricato: uso la visura e la relazione di esempio.")
    st.header("AI")
    modalita = st.radio(
        "Dove va il testo pseudonimizzato",
        ["simulata", "api"],
        format_func=lambda m: {"simulata": "AI simulata (nessun invio)", "api": "API compatibile OpenAI"}[m],
        help="L'API si configura con PRIVACY_AI_URL, PRIVACY_AI_MODELLO e PRIVACY_AI_CHIAVE: "
        "un modello in locale (Ollama) o un fornitore con server in UE.",
    )
    anche_visure = st.checkbox("Manda all'AI anche le visure", value=False)

if caricati:
    cartella = Path(tempfile.mkdtemp())
    documenti = []
    for f in caricati:
        percorso = cartella / Path(f.name).name
        percorso.write_bytes(f.getvalue())
        try:
            documenti.append(leggi_pdf(percorso))
        except ValueError as e:
            st.warning(str(e))
else:
    documenti = [leggi_pdf(ESEMPI / "visura.pdf"), leggi_pdf(ESEMPI / "relazione.pdf")]

if not documenti:
    st.stop()

registro = Path(tempfile.mkdtemp()) / "elaborazioni.jsonl"
try:
    esiti, p = elabora(documenti, modalita, anche_visure, registro)
except UscitaBloccata as e:
    st.error("Invio bloccato: nel testo da inviare sono rimasti dati personali.")
    st.write(e.problemi)
    st.stop()
except OSError as e:
    st.error(f"Il servizio AI non risponde: {e}")
    st.stop()

caveau = dict(p.caveau)
valori_veri = list(caveau.values()) + [v for persona in p.persone for v in persona.varianti]

for esito in esiti:
    doc: Documento = esito.documento
    st.divider()
    st.subheader(f"📄 {doc.nome}")
    st.caption(f"{doc.pagine} pagina/e · impronta SHA-256 {doc.impronta[:16]}…")

    if esito.visura:
        st.success("Visura riconosciuta: dati letti con un parser in locale, **nessun invio all'AI**.")
        v = esito.visura
        st.markdown(f"**Comune:** {v.comune} ({v.codice_comune})")
        st.dataframe([i.__dict__ for i in v.intestatari], width="stretch", hide_index=True)
        st.dataframe([i.__dict__ for i in v.immobili], width="stretch", hide_index=True)
        with st.expander("Testo estratto"):
            st.markdown(evidenzia(doc.testo, valori_veri), unsafe_allow_html=True)
        if esito.testo_inviato is None:
            continue

    sinistra, destra = st.columns(2)
    with sinistra:
        st.markdown("**① Documento originale** · resta in azienda")
        st.markdown(evidenzia(doc.testo, valori_veri), unsafe_allow_html=True)
    with destra:
        st.markdown("**② Testo inviato all'AI** · è tutto quello che esce")
        st.markdown(evidenzia(esito.testo_inviato), unsafe_allow_html=True)
    st.caption("Sostituzioni: " + ", ".join(f"{k.lower().replace('_', ' ')} {n}" for k, n in esito.sostituzioni.items()))

    sinistra, destra = st.columns(2)
    with sinistra:
        st.markdown("**③ Bozza scritta dall'AI** · contiene solo segnaposto")
        st.markdown(evidenzia(come_testo(esito.bozza_ai)), unsafe_allow_html=True)
    with destra:
        st.markdown("**④ Bozza con i dati veri** · rimessi in locale")
        st.markdown(evidenzia(come_testo(esito.bozza_finale), valori_veri), unsafe_allow_html=True)

st.divider()
st.subheader("📝 Relazione generata")
st.markdown(
    "Il documento Word si compone **in locale**: i dati catastali e gli intestatari arrivano dal parser della "
    "visura, stato dei luoghi, criticità e verifiche dalla bozza dell'AI con i dati veri rimessi. "
    "L'AI non vede mai il documento finito. È una bozza modificabile: il tecnico la rilegge e la firma."
)
st.download_button(
    "⬇️ Scarica la relazione (.docx)",
    genera_relazione(esiti, p),
    file_name="relazione-accertamento.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    type="primary",
)

st.divider()
sinistra, destra = st.columns(2)
with sinistra:
    st.subheader("🗝️ Caveau")
    st.caption("Tabella segnaposto → valore vero. Solo in memoria, mai inviata, svuotata a fine elaborazione.")
    st.dataframe(
        [{"segnaposto": k, "valore vero": v} for k, v in caveau.items()], width="stretch", hide_index=True
    )
with destra:
    st.subheader("📋 Registro delle elaborazioni")
    st.caption("Cosa è stato elaborato e dove è andato. Nessun dato personale: il documento è identificato dall'impronta.")
    righe = [json.loads(r) for r in registro.read_text(encoding="utf-8").splitlines()]
    st.dataframe(righe, width="stretch", hide_index=True)

p.dimentica()
