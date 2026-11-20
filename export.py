"""Exports : promotion au format CSV (compatible Excel) et relevé de notes HTML imprimable.

Aucune bibliothèque PDF n'étant requise, le relevé est un fichier HTML stylisé :
le bouton « Imprimer / Enregistrer en PDF » du navigateur permet d'obtenir un PDF.
"""

from __future__ import annotations

import csv
import html
import re
from datetime import datetime
from pathlib import Path
from string import Template

import calculs

DOSSIER_EXPORTS = Path(__file__).resolve().parent / "exports"
FORMATION = "Master 1 DAT"


def _nombre_fr(valeur, decimales=2) -> str:
    """12.5 -> « 12,50 » (Excel en français reconnaît la virgule décimale)."""
    return "" if valeur is None else f"{valeur:.{decimales}f}".replace(".", ",")


def _cellule_sure(texte: str) -> str:
    """Neutralise l'injection de formules dans Excel (=, +, -, @ en début de cellule)."""
    texte = str(texte)
    return "'" + texte if texte[:1] in ("=", "+", "-", "@") else texte


def _trier_par_rang(promotion):
    return sorted(promotion, key=lambda l: (l["rang"] is None, l["rang"] or 0,
                                            l["nom"].casefold(), l["prenom"].casefold()))


def exporter_csv(db, chemin) -> int:
    """Export global de la promotion. Séparateur « ; », encodage UTF-8 avec BOM pour Excel."""
    matieres = db.lister_matieres()
    promotion = _trier_par_rang(db.tableau_promotion())
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(["Rang", "Nom", "Prénom"]
                          + [f"{m['nom']} (coef {m['coefficient']:g})" for m in matieres]
                          + ["Moyenne pondérée", "Mention", "Décision", "Appréciation générale"])
        for l in promotion:
            moyenne = l["moyenne"]
            decision = "" if moyenne is None else (
                "Admis" if moyenne >= calculs.SEUIL_ADMISSION else "Ajourné")
            ecrivain.writerow(
                [l["rang"] or "", _cellule_sure(l["nom"]), _cellule_sure(l["prenom"])]
                + [_nombre_fr(l["notes"].get(m["id"])) for m in matieres]
                + [_nombre_fr(moyenne), calculs.mention(moyenne) if moyenne is not None else "",
                   decision, _cellule_sure(l["appreciation"])])
    return len(promotion)


# --------------------------------------------------------------------- relevé HTML
_GABARIT = Template("""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Relevé de notes — $nom_complet</title>
<style>
  :root { --bleu: #1f538d; --texte: #1c2833; --doux: #5d6d7e; --bord: #d5dbe3; --fond: #eef1f5; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--fond); color: var(--texte);
         font: 14px/1.5 "Segoe UI", Roboto, Arial, sans-serif; }
  .page { max-width: 820px; margin: 32px auto; background: #fff; padding: 40px 48px;
          border-radius: 10px; box-shadow: 0 4px 18px rgba(0,0,0,.08); }
  header { display: flex; justify-content: space-between; align-items: flex-end;
           border-bottom: 3px solid var(--bleu); padding-bottom: 14px; margin-bottom: 24px; }
  h1 { margin: 0; color: var(--bleu); font-size: 26px; letter-spacing: .5px; }
  h2 { color: var(--bleu); font-size: 16px; margin: 28px 0 8px; }
  .sous, .date { color: var(--doux); margin: 4px 0 0; }
  .identite { display: flex; gap: 40px; background: var(--fond); padding: 14px 18px; border-radius: 8px; }
  .identite span { display: block; font-size: 12px; color: var(--doux); text-transform: uppercase; }
  .identite strong { font-size: 17px; }
  table { width: 100%; border-collapse: collapse; margin-top: 22px; }
  th { background: var(--bleu); color: #fff; text-align: left; padding: 9px 10px; font-weight: 600; }
  td { padding: 9px 10px; border-bottom: 1px solid var(--bord); vertical-align: top; }
  tbody tr:nth-child(even) td { background: #f7f9fb; }
  tfoot td { font-weight: 700; border-top: 2px solid var(--bleu); border-bottom: none; }
  .c { text-align: center; white-space: nowrap; }
  .echec { color: #C0392B; font-weight: 600; }
  .absent { color: var(--doux); font-style: italic; }
  .synthese { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 24px; }
  .carte { border: 1px solid var(--bord); border-radius: 8px; padding: 12px; text-align: center; }
  .carte span { display: block; font-size: 12px; color: var(--doux); text-transform: uppercase; }
  .carte strong { font-size: 20px; color: var(--bleu); }
  .carte.admis strong { color: #1E8449; } .carte.ajourne strong { color: #C0392B; }
  .appreciation p { border-left: 4px solid var(--bleu); background: var(--fond);
                    margin: 0; padding: 12px 16px; border-radius: 0 6px 6px 0; white-space: pre-wrap; }
  footer { display: flex; justify-content: space-between; margin-top: 48px; color: var(--doux); }
  footer div { border-top: 1px solid var(--bord); padding-top: 6px; width: 45%; }
  .imprimer { display: block; margin: 0 auto 32px; padding: 10px 22px; border: 0; border-radius: 6px;
              background: var(--bleu); color: #fff; font-size: 14px; cursor: pointer; }
  @media print {
    body { background: #fff; }
    .page { box-shadow: none; margin: 0; max-width: none; padding: 0; }
    .imprimer { display: none; }
  }
</style>
</head>
<body>
<div class="page">
  <header>
    <div>
      <h1>Relevé de notes</h1>
      <p class="sous">$formation · Année universitaire $annee</p>
    </div>
    <p class="date">Édité le $date</p>
  </header>

  <section class="identite">
    <div><span>Nom</span><strong>$nom</strong></div>
    <div><span>Prénom</span><strong>$prenom</strong></div>
    <div><span>N° étudiant</span><strong>$numero</strong></div>
  </section>

  <table>
    <thead><tr><th>Matière</th><th class="c">Coef.</th><th class="c">Note /20</th>
      <th class="c">Points</th><th>Appréciation</th></tr></thead>
    <tbody>
$lignes
    </tbody>
    <tfoot><tr><td>Total (matières évaluées)</td><td class="c">$total_coef</td><td></td>
      <td class="c">$total_points</td><td></td></tr></tfoot>
  </table>

  <section class="synthese">
    <div class="carte"><span>Moyenne pondérée</span><strong>$moyenne</strong></div>
    <div class="carte"><span>Rang</span><strong>$rang</strong></div>
    <div class="carte"><span>Mention</span><strong>$mention</strong></div>
    <div class="carte $classe_decision"><span>Décision</span><strong>$decision</strong></div>
  </section>

  <section class="appreciation">
    <h2>Appréciation générale</h2>
    <p>$appreciation</p>
  </section>

  <footer>
    <div>L'étudiant(e)</div>
    <div>Le responsable de formation</div>
  </footer>
</div>
<button class="imprimer" onclick="window.print()">🖨 Imprimer / Enregistrer en PDF</button>
</body>
</html>
""")


def _annee_universitaire(date: datetime) -> str:
    debut = date.year if date.month >= 9 else date.year - 1
    return f"{debut}-{debut + 1}"


def _nom_fichier(texte: str) -> str:
    return re.sub(r"[^\w-]+", "_", texte, flags=re.UNICODE).strip("_") or "etudiant"


def generer_releve_html(db, etudiant_id, dossier=DOSSIER_EXPORTS) -> Path:
    """Crée le relevé individuel et renvoie le chemin du fichier HTML."""
    promotion = db.tableau_promotion()
    fiche = next((l for l in promotion if l["id"] == etudiant_id), None)
    if fiche is None:
        raise ValueError("Étudiant introuvable.")
    details = db.notes_etudiant(etudiant_id)
    matieres = db.lister_matieres()
    effectif_classe = sum(1 for l in promotion if l["moyenne"] is not None)

    e = html.escape
    lignes, total_coef, total_points = [], 0.0, 0.0
    for m in matieres:
        note = details.get(m["id"])
        if note is None:
            lignes.append(f'      <tr><td>{e(m["nom"])}</td><td class="c">{m["coefficient"]:g}</td>'
                          f'<td class="c absent">—</td><td class="c absent">—</td>'
                          f'<td class="absent">Non évaluée</td></tr>')
            continue
        points = note["valeur"] * m["coefficient"]
        total_coef += m["coefficient"]
        total_points += points
        classe = ' echec' if note["valeur"] < calculs.SEUIL_ADMISSION else ''
        lignes.append(f'      <tr><td>{e(m["nom"])}</td><td class="c">{m["coefficient"]:g}</td>'
                      f'<td class="c{classe}">{_nombre_fr(note["valeur"])}</td>'
                      f'<td class="c">{_nombre_fr(points)}</td><td>{e(note["appreciation"])}</td></tr>')
    if not matieres:
        lignes.append('      <tr><td colspan="5" class="absent">Aucune matière définie.</td></tr>')

    moyenne = fiche["moyenne"]
    if moyenne is None:
        decision, classe_decision = "—", ""
    elif moyenne >= calculs.SEUIL_ADMISSION:
        decision, classe_decision = "Admis", "admis"
    else:
        decision, classe_decision = "Ajourné", "ajourne"

    date = datetime.now()
    contenu = _GABARIT.substitute(
        nom_complet=e(f'{fiche["prenom"]} {fiche["nom"]}'.strip()),
        nom=e(fiche["nom"]), prenom=e(fiche["prenom"]) or "—",
        numero=f'{etudiant_id:05d}', formation=e(FORMATION),
        annee=_annee_universitaire(date), date=date.strftime("%d/%m/%Y à %H:%M"),
        lignes="\n".join(lignes),
        total_coef=f"{total_coef:g}", total_points=_nombre_fr(total_points) if total_coef else "—",
        moyenne=f"{_nombre_fr(moyenne)} /20" if moyenne is not None else "—",
        rang=f'{calculs.libelle_rang(fiche["rang"], podium=False)} / {effectif_classe}' if fiche["rang"] else "—",
        mention=e(calculs.mention(moyenne)), decision=decision, classe_decision=classe_decision,
        appreciation=e(fiche["appreciation"]) or '<span class="absent">Aucune appréciation.</span>',
    )
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f'releve_{_nom_fichier(fiche["nom"])}_{_nom_fichier(fiche["prenom"])}.html'
    chemin.write_text(contenu, encoding="utf-8")
    return chemin
