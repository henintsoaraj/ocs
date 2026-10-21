# OCS — moteur de taxation en temps réel

![tests](https://github.com/henintsoaraj/ocs/actions/workflows/tests.yml/badge.svg)

Le cœur d'un **Online Charging System** (OCS) : le composant qui, chez un opérateur télécom, décide en temps réel si un abonné a le droit de consommer, bloque son crédit pendant l'appel, prélève la consommation réelle à la fin, et trace chaque appel.

Projet personnel construit pas à pas pour approfondir la fiabilité des systèmes (SRE) : concurrence, transactions, idempotence, tests automatisés, CI et migrations, appliqués à un domaine où une erreur se compte en argent.

---

## Le principe : réserver, consommer, prélever

Comme la caution d'un hôtel, le moteur **bloque** du crédit au début d'un appel, puis **prélève** ce qui a vraiment été consommé et **débloque** le reste à la fin.

```
                         balance   reserved   disponible
Départ                     100         0          100
Début d'appel : réserve 60 100        60           40
Fin d'appel : consommé 40   60         0           60
```

Les montants sont des entiers en centimes : jamais de nombres à virgule pour de l'argent.

## Les garanties

Chaque ligne de ce tableau est vérifiée par un test automatisé, à chaque push.

| Situation | Comportement |
|---|---|
| Réservation normale | Le crédit est bloqué de façon atomique |
| Crédit insuffisant / compte inconnu | Deux refus distincts (`CREDIT_LIMIT_REACHED`, `UNKNOWN_ACCOUNT`) |
| 100 réservations simultanées | Jamais un centime réservé de trop |
| Réservation retransmise par le réseau | Même réponse, crédit bloqué une seule fois |
| Fin d'appel | Prélève le consommé, débloque tout le réservé |
| Fin d'appel retransmise | Reconnue grâce au CDR : aucun double débit |
| Consommation annoncée supérieure à la réservation | Plafonnée au réservé, écart tracé dans le CDR |
| Appel fantôme (fin d'appel jamais reçue) | Crédit libéré à l'expiration, sans prélèvement |
| Chaque appel terminé ou expiré | Un CDR, jamais modifié ni supprimé |

## L'expérience : la condition de course, mesurée

Un compte à 100 centimes reçoit **100 demandes simultanées** de 10 centimes (50 threads, une connexion chacun). Une seule réponse est correcte : 10 acceptées, 90 refusées.

| | Version naïve | Version atomique |
|---|---|---|
| Logique | Lire le solde, vérifier en Python, écrire | Vérifier et écrire en une seule instruction SQL |
| Appels autorisés | 98 à 100 | **10** |
| Communication autorisée | jusqu'à 1 000 centimes | **100 centimes** |
| `reserved` à la fin | 30 à 90, change à chaque lancement | **100**, à chaque lancement |

La version naïve lit une valeur déjà périmée : des dizaines de threads voient `reserved = 20`, valident, puis écrivent tous `30`. C'est une **mise à jour perdue** : des appels autorisés sans aucun crédit derrière, et un compte qui se croit encore riche. La contrainte `CHECK` de la base ne voit rien, puisque `reserved` ne dépasse jamais `balance` : les données sont fausses sans être impossibles. Et avec une seule requête à la fois, la version naïve passe tous les tests.

La version atomique laisse PostgreSQL vérifier et écrire en une seule instruction, sur une ligne qu'il verrouille :

```sql
UPDATE accounts
SET reserved = reserved + %s
WHERE id = %s
  AND balance - reserved >= %s
```

## Architecture

```
app/
├── engine.py        reserve(), terminate(), expire_reservations()
├── migrate.py       applique les migrations manquantes
└── expire_job.py    tâche planifiée d'expiration
migrations/          schéma versionné (001, 002, 003...)
tests/               11 tests pytest sur une base de test isolée
.github/workflows/   CI : migrations + tests à chaque push
```

Trois tables :

- **`accounts`** : `balance` (crédit) et `reserved` (bloqué), avec une contrainte `CHECK (reserved <= balance)` comme dernier garde-fou.
- **`reservations`** : une ligne par appel en cours, avec sa date d'expiration.
- **`cdrs`** : un ticket par appel terminé ou expiré, en ajout seul. `used` (annoncé par le réseau) et `charged` (prélevé) sont séparés, et `used` vaut `NULL` quand la consommation est inconnue.

## Choix de conception

- **Une seule transaction par opération** : prélèvement, suppression de la réservation et écriture du CDR réussissent ensemble ou pas du tout.
- **Le `DELETE ... RETURNING` comme verrou naturel** : une réservation ne peut être supprimée qu'une fois, donc une fin d'appel et une expiration simultanées ne peuvent jamais la traiter deux fois.
- **Idempotence face aux retransmissions** : quand le réseau rejoue une demande dont la réponse s'est perdue, il reçoit la même réponse que la première fois, sans effet supplémentaire.
- **Expiration sans prélèvement** : la consommation d'un appel fantôme est inconnue ; l'opérateur l'absorbe en faveur de l'abonné, et le CDR `EXPIRED` la rend visible et mesurable.
- **Migrations versionnées** : chaque base (travail, test, CI) sait elle-même quelles évolutions de schéma elle a reçues.
- **Base de test séparée** : vidée avant chaque test, protégée par un garde-fou qui refuse de tourner sur une base dont le nom ne finit pas par `_test`.

## Lancer le projet

Prérequis : Docker, Python 3.12.

```bash
docker compose up -d
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://ocs:MOT_DE_PASSE@localhost:5432/ocs"
export TEST_DATABASE_URL="postgresql://ocs:MOT_DE_PASSE@localhost:5432/ocs_test"

docker compose exec postgres psql -U ocs -d ocs -c "CREATE DATABASE ocs_test;"
python app/migrate.py
python app/migrate.py "$TEST_DATABASE_URL"

pytest -v
```

## Limites

Ce projet est le moteur, pas un OCS complet. Il n'implémente pas le protocole Diameter (Gy/Ro), la tarification (forfaits, paliers), ni la haute disponibilité. Les montants réservés et consommés sont fournis directement par l'appelant.
