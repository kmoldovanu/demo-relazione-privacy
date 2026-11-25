"""Riga di comando: python -m privacy_ai esempi/visura.pdf esempi/relazione.pdf"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ai import come_testo
from .documento import genera_relazione
from .estrazione import leggi_pdf
from .flusso import UscitaBloccata, elabora

VERDE, GIALLO, ROSSO, GRIGIO, GRASSETTO, FINE = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"


def titolo(numero: str, testo: str, dove: str) -> None:
    colore = VERDE if dove == "in locale" else GIALLO
    print(f"\n{GRASSETTO}{numero}. {testo}{FINE}  {colore}[{dove}]{FINE}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", help="uno o più PDF")
    parser.add_argument("--ai", choices=["simulata", "api"], default="simulata", help="dove mandare il testo")
    parser.add_argument("--ai-anche-su-visure", action="store_true", help="manda all'AI anche le visure")
    parser.add_argument("--documento", default="relazione-generata.docx", help="dove salvare la relazione Word")
    args = parser.parse_args()

    documenti = [leggi_pdf(f) for f in args.pdf]
    try:
        esiti, p = elabora(documenti, args.ai, args.ai_anche_su_visure)
    except UscitaBloccata as e:
        print(f"{ROSSO}{GRASSETTO}Invio bloccato:{FINE} nel testo sono rimasti dati personali:")
        for problema in e.problemi:
            print(f"  - {problema}")
        return 1

    for esito in esiti:
        doc = esito.documento
        print(f"\n{GRASSETTO}{'═' * 70}\n{doc.nome}{FINE}  {GRIGIO}{doc.pagine} pag., sha256 {doc.impronta[:12]}…{FINE}")
        titolo("1", "Testo estratto dal PDF", "in locale")
        print(GRIGIO + doc.testo.strip() + FINE)

        if esito.visura:
            titolo("2", "Visura: dati letti con un parser, senza AI", "in locale")
            print(json.dumps(esito.visura.come_dict(), indent=2, ensure_ascii=False))
            if esito.testo_inviato is None:
                print(f"{VERDE}Nessun invio all'AI: per un documento a formato fisso non serve.{FINE}")
                continue

        titolo("3", f"Pseudonimizzazione: {esito.sostituzioni}", "in locale")
        titolo("4", "Testo inviato all'AI (è tutto quello che esce)", "esce" if args.ai == "api" else "simulato")
        print(esito.testo_inviato.strip())
        titolo("5", "Bozza scritta dall'AI, con i segnaposto", "esce" if args.ai == "api" else "simulato")
        print(come_testo(esito.bozza_ai))
        titolo("6", "Bozza con i dati veri rimessi", "in locale")
        print(come_testo(esito.bozza_finale))

    titolo("7", "Relazione Word composta con i dati veri", "in locale")
    Path(args.documento).write_bytes(genera_relazione(esiti, p))
    print(f"Salvata in {args.documento}")

    print(f"\n{GRASSETTO}Caveau (solo in memoria, cancellato ora):{FINE}")
    for segnaposto, valore in p.caveau.items():
        print(f"  {segnaposto:<20} {GRIGIO}{valore}{FINE}")
    p.dimentica()
    print(f"\nRegistro delle elaborazioni: registro/elaborazioni.jsonl {GRIGIO}(senza dati personali){FINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
