# Durance Luberon – Intégration Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Récupère automatiquement votre consommation d'eau depuis le portail abonnés Durance Luberon et l'expose comme capteurs dans Home Assistant.

## Capteurs disponibles

| Capteur | Description | Unité |
|---------|-------------|-------|
| `sensor.index_compteur_eau` | Index absolu du compteur (croissant en continu) | m³ |
| `sensor.consommation_eau_journaliere` | Consommation du dernier jour relevé | m³ |
| `sensor.consommation_eau_mensuelle` | Consommation totale du mois en cours | m³ |
| `sensor.dernier_releve_eau` | Date du dernier relevé | date |

## Installation via HACS

1. Ouvrir HACS → **Intégrations** → **⋮** → **Dépôts personnalisés**
2. Ajouter l'URL : `https://github.com/alexsxb/duralub_eau` en tant qu'**Intégration**
3. Rechercher et installer l'intégration
4. Redémarrer Home Assistant
5. **Paramètres → Appareils et services → Ajouter une intégration → Durance Luberon**

## Installation manuelle

Copier le dossier `custom_components/durance_luberon/` dans `config/custom_components/` de votre installation Home Assistant, puis redémarrer.

## Configuration

Lors de la première configuration, seulement deux informations sont nécessaires :

| Champ | Description |
|-------|-------------|
| Adresse e-mail | Identifiant de connexion au portail |
| Mot de passe | Mot de passe du portail |
| Intervalle | Fréquence de mise à jour en minutes (recommandé : 360 = 6h) |

L'identifiant du compteur (Teleindex) est récupéré **automatiquement** après connexion — aucune manipulation dans le portail ou les outils développeur n'est nécessaire.

## Intégration Énergie Home Assistant

Le capteur `sensor.index_compteur_eau` est de type `total_increasing` et peut être ajouté directement dans :

**Paramètres → Énergie → Consommation d'eau → Ajouter un compteur d'eau**

Home Assistant calculera automatiquement la consommation à partir des différences d'index.

## Exemple de carte Lovelace

```yaml
type: entities
title: Consommation d'eau
entities:
  - entity: sensor.index_compteur_eau
  - entity: sensor.consommation_eau_journaliere
  - entity: sensor.consommation_eau_mensuelle
  - entity: sensor.dernier_releve_eau
```

## Licence

MIT
