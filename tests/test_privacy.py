from pathlib import Path

import pytest

from privacy_ai.estrazione import leggi_pdf
from privacy_ai.flusso import UscitaBloccata, elabora
from privacy_ai.pseudonimizza import Pseudonimizzatore
from privacy_ai.visura import cf_valido, leggi_visura

ESEMPI = Path(__file__).resolve().parent.parent / "esempi"
VERI = [
    "Giraudo", "Elena", "Bertola", "Luca", "Martini", "elena.giraudo@esempio.it",
    "IT60X0542811101000000123456", "GRDLNE78C54H727F", "333 812 4471", "Glicini", "02/09/1975", "Fossano",
]


@pytest.fixture(scope="module")
def esiti(tmp_path_factory):
    documenti = [leggi_pdf(ESEMPI / "visura.pdf"), leggi_pdf(ESEMPI / "relazione.pdf")]
    return elabora(documenti, "simulata", file_registro=tmp_path_factory.mktemp("r") / "r.jsonl")


def test_nessun_dato_personale_esce(esiti):
    risultati, _ = esiti
    inviato = risultati[1].testo_inviato
    for valore in VERI:
        assert valore.lower() not in inviato.lower(), valore


def test_la_visura_non_va_all_ai(esiti):
    risultati, _ = esiti
    assert risultati[0].visura is not None
    assert risultati[0].testo_inviato is None


def test_la_risposta_torna_con_i_dati_veri(esiti):
    risultati, _ = esiti
    finale = risultati[1].risposta_finale
    assert "Giraudo Elena" in finale
    assert "[PERSONA_" not in finale


def test_stesso_dato_stesso_segnaposto():
    p = Pseudonimizzatore()
    testo = "Sig.ra Elena Giraudo. Poi la Sig.ra Giraudo ha firmato. Tel 333 812 4471 e 333-812-4471."
    p.impara(testo)
    uscita = p.applica(testo)
    assert uscita.count("[PERSONA_1]") == 2
    assert uscita.count("[TELEFONO_1]") == 2
    assert p.reidentifica("[PERSONA_1]") == "Elena Giraudo"


def test_il_controllo_blocca_se_resta_qualcosa(tmp_path):
    p = Pseudonimizzatore()
    p.impara("Sig. Luca Bertola")
    p.applica("Sig. Luca Bertola")
    assert p.verifica_uscita("scrivere a Bertola, CF BRTLCU75P02D742W")


def test_invio_bloccato_ferma_il_flusso(monkeypatch, tmp_path):
    monkeypatch.setattr(Pseudonimizzatore, "applica", lambda self, t: t)  # simula un errore di sostituzione
    with pytest.raises(UscitaBloccata):
        elabora([leggi_pdf(ESEMPI / "relazione.pdf")], file_registro=tmp_path / "r.jsonl")


def test_lettura_visura():
    visura = leggi_visura(leggi_pdf(ESEMPI / "visura.pdf").testo)
    assert visura.codice_comune == "D205"
    assert [i.nome for i in visura.intestatari] == ["GIRAUDO ELENA", "BERTOLA LUCA"]
    assert all(i.codice_fiscale_valido for i in visura.intestatari)
    assert [i.categoria for i in visura.immobili] == ["A/2", "C/6"]
    assert visura.immobili[0].rendita_euro == 588.76


def test_codice_fiscale():
    assert cf_valido("GRDLNE78C54H727F")
    assert not cf_valido("GRDLNE78C54H727A")


def test_registro_senza_dati_personali(tmp_path):
    registro = tmp_path / "r.jsonl"
    elabora([leggi_pdf(ESEMPI / "relazione.pdf")], file_registro=registro)
    contenuto = registro.read_text().lower()
    for valore in VERI:
        assert valore.lower() not in contenuto
