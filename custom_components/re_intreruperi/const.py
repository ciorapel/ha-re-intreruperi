"""Constante pentru integrarea Rețele Electrice - Întreruperi."""

DOMAIN = "re_intreruperi"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POD = "pod"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 3600  # secunde
MIN_SCAN_INTERVAL = 900       # 15 min - portalul e un site web, nu un API
MAX_SCAN_INTERVAL = 86400

BASE_URL = "https://contulmeu.reteleelectrice.ro"
LOGIN_PAGE = f"{BASE_URL}/PEDRO_SiteLogin"
VF_OUTAGES = f"{BASE_URL}/PED_ProxyCallWSAsynPowerOutages_VF"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)
