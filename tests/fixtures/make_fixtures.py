"""Build synthetic case-fixture PDFs.

These stand in for real Case 1 data so the whole pipeline can be exercised
offline. All names, numbers and facts are invented. Layout mimics Québec
CNESST medical-legal records: consultation note, imaging report, CNESST
decision, plus adversarial pages (blank, image-only, OCR garbage).
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

CONSULTATION_P1 = """CLINIQUE MÉDICALE SAINT-LAURENT
1234, boulevard Fictif, Montréal (Québec)  H2X 1Y4
Téléphone : 514 555-0182

NOTE DE CONSULTATION MÉDICALE

Patient : Jean Tremblay
NAM : TREJ 8001 0512
Dossier CNESST : 123456789

Date de la consultation : 16 juillet 2025

Le travailleur consulte pour une recrudescence de lombalgie à la suite de
l'accident du travail survenu le 3 mars 2025. Il rapporte une augmentation
de la douleur lombaire irradiant au membre inférieur droit depuis environ
deux semaines.
"""

CONSULTATION_P2 = """Examen : douleur à la palpation L4-L5, Lasègue positif à droite à 45 degrés.

Impression : entorse lombaire avec sciatalgie droite, possible récidive.

Plan : prescription d'une IRM lombaire, arrêt de travail jusqu'au
15 août 2025, physiothérapie deux fois par semaine.

Dre Marie Gagnon, omnipraticienne
Signé le 16 juillet 2025
"""

IMAGING_P1 = """CENTRE D'IMAGERIE FICTIF DE MONTRÉAL

IRM DE LA COLONNE LOMBAIRE

Patient : Jean Tremblay
NAM : TREJ 8001 0512
Date de l'examen : 22 juillet 2025
Médecin référent : Dre Marie Gagnon

Technique : séquences sagittales et axiales T1 et T2.

Constatations : discopathie dégénérative L4-L5 avec protrusion discale
postéro-latérale droite de 4 mm comprimant la racine L5 droite.

Conclusion : protrusion discale L4-L5 droite avec conflit radiculaire L5.

Dr Paul Lefebvre, radiologiste
"""

DECISION_P1 = """CNESST
Commission des normes, de l'équité, de la santé et de la sécurité du travail

DÉCISION

Travailleur : Jean Tremblay
Dossier : 123456789
Employeur : Entrepôt Fictif inc.

Décision rendue le 5 août 2025

Objet : admissibilité de la réclamation — récidive, rechute ou aggravation
"""

DECISION_P2 = """Après analyse du dossier, la Commission accepte la réclamation du
travailleur pour une récidive, rechute ou aggravation survenue le
2 juillet 2025, en relation avec l'événement d'origine du 3 mars 2025.

Diagnostic accepté : entorse lombaire avec sciatalgie droite.
Diagnostic refusé : hernie discale L4-L5.

Le travailleur a droit aux indemnités prévues par la Loi.

Vous pouvez demander la révision de cette décision dans les 30 jours.

Direction de l'indemnisation
"""

GARBAGE_TEXT = "]]§¶## @@©® ~~ ||| ///%%% ^^^ )))((( ::: ;;; ***\n" * 30


def _add_text_page(doc: fitz.Document, text: str) -> None:
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 792), text, fontsize=10, fontname="helv")


def _add_image_only_page(doc: fitz.Document, text: str) -> None:
    """Render text into a raster image and embed it, leaving no native text layer."""
    tmp = fitz.open()
    _add_text_page(tmp, text)
    pix = tmp[0].get_pixmap(dpi=150)
    tmp.close()
    page = doc.new_page()
    page.insert_image(page.rect, pixmap=pix)


def build_fixtures(target: Path) -> dict[str, int]:
    """Create fixture PDFs in ``target``. Returns {filename: page_count}."""
    target.mkdir(parents=True, exist_ok=True)

    # bundle_01: consultation (2p) + imaging (1p) + blank page
    b1 = fitz.open()
    _add_text_page(b1, CONSULTATION_P1)
    _add_text_page(b1, CONSULTATION_P2)
    _add_text_page(b1, IMAGING_P1)
    b1.new_page()  # blank
    b1.save(target / "bundle_01.pdf")
    b1.close()

    # bundle_02: CNESST decision (2p) + image-only scan + garbage page
    b2 = fitz.open()
    _add_text_page(b2, DECISION_P1)
    _add_text_page(b2, DECISION_P2)
    _add_image_only_page(
        b2,
        "PHYSIOTHÉRAPIE FICTIVE DE MONTRÉAL\n"
        "Note de traitement\n\n"
        "Patient : Jean Tremblay\n"
        "Date du traitement : 10 juillet 2025\n\n"
        "Le patient se présente pour sa séance de physiothérapie pour la région\n"
        "lombaire. Les exercices de renforcement et les étirements sont poursuivis.\n"
        "La douleur est en diminution depuis la dernière visite et la mobilité du\n"
        "tronc est améliorée. Le plan de traitement est maintenu à raison de deux\n"
        "séances par semaine jusqu'à la prochaine évaluation médicale.",
    )
    _add_text_page(b2, GARBAGE_TEXT)
    b2.save(target / "bundle_02.pdf")
    b2.close()

    return {"bundle_01.pdf": 4, "bundle_02.pdf": 4}


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/generated")
    print(build_fixtures(out))
