"""Constantes pour l'intégration Durance Luberon."""

DOMAIN = "durance_luberon"

# Clés de configuration
CONF_LOGIN         = "login"
CONF_PASSWORD      = "password"
CONF_SCAN_INTERVAL = "scan_interval"
# CONF_TELEINDEX_ID supprimé – découvert automatiquement via /contrat

# API
API_HOST = "espace-personnel.duranceluberon.fr"
API_BASE = "https://espace-personnel.duranceluberon.fr/api/v1"
API_ID   = "4f3443744f61c978230053e8370e4c9bd4f0f19f73d44a82624f23943723dee0@iclients-17254"

# Valeurs par défaut
DEFAULT_SCAN_INTERVAL = 360   # minutes (6 heures)
DEFAULT_NAME          = "Durance Luberon"
