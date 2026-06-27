# AstroCarnet Sky Agenda

Base distante gratuite pour l’Agenda du ciel J+7 de l’app AstroCarnet DWARF.

## Ce que ça fait

Ce dépôt génère automatiquement un fichier :

```text
sky_agenda.json
```

L’app Flutter lit ensuite ce fichier via :

```text
https://raw.githubusercontent.com/williamgosc/astrocarnet-sky-agenda/main/sky_agenda.json
```

## Source des données

Le générateur utilise :

```text
Python + Skyfield
```

Aucune clé API, aucun abonnement, aucun service payant.

## Ce qui est généré

Pour chaque jour :

```text
- Lune visible à partir de...
- Mercure visible à partir de...
- Vénus visible à partir de...
- Mars visible à partir de...
- Jupiter visible à partir de...
- Saturne visible à partir de...
- pluie de météores si un pic tombe bientôt
```

L’app n’affiche pas altitude, azimut, séparation angulaire ou données techniques.

## Lieu utilisé

Par défaut :

```text
Saint-Germain / Troyes
Latitude : 48.2564
Longitude : 4.0296
Fuseau : Europe/Paris
```

Pour Troyes pur, tu peux remplacer dans `generate_sky_agenda.py` :

```text
LATITUDE = 48.2973
LONGITUDE = 4.0744
```

Mais la différence entre Troyes et Saint-Germain est très faible pour ce type d’agenda simple.

## Lancer à la main sur GitHub

Dans le dépôt GitHub :

```text
Actions
→ Update sky agenda
→ Run workflow
```

Après quelques dizaines de secondes, `sky_agenda.json` sera mis à jour.

## Mise à jour automatique

Le workflow tourne tous les matins via GitHub Actions.
