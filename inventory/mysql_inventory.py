#!/usr/bin/env python3

import argparse
import json
import logging
import os
import sys
import unicodedata

try:
    import mysql.connector
except ImportError:
    print(
        json.dumps(
            {"error": "mysql-connector-python non installe dans l'EE"},
            ensure_ascii=False,
        )
    )
    sys.exit(1)


# ============================================================
# CONFIGURATION LOG
# ============================================================

log_level = os.environ.get("MYSQL_INVENTORY_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

log = logging.getLogger(__name__)


# ============================================================
# UTILITAIRES
# ============================================================

def debug_environment():
    """
    Affiche les variables MYSQL/AWX reçues par AWX.
    Le mot de passe est masqué.
    """

    print("\n=== DEBUG MYSQL ENV ===", file=sys.stderr)

    for key, value in sorted(os.environ.items()):

        if "MYSQL" in key.upper() or "AWX" in key.upper():

            if "PASSWORD" in key.upper():
                print(f"{key}=********", file=sys.stderr)

            else:
                print(f"{key}={value}", file=sys.stderr)

    print("=======================\n", file=sys.stderr)


def env_or_fail(name, default=None, required=False):
    """
    Récupère une variable d'environnement.

    Si required=True et que la variable est absente,
    une exception est générée.
    """

    value = os.environ.get(name, default)

    if required and not value:
        raise RuntimeError(
            f"Variable d'environnement requise absente: {name}"
        )

    return value


def normalize_group_name(value, prefix=""):
    """
    Transforme une valeur MySQL en nom de groupe Ansible propre.

    Exemple :

        "Déconnecté"
            -> "status_deconnecte"

        "Switch Accès"
            -> "role_switch_acces"

        "Hewlett Packard"
            -> "vendor_hewlett_packard"
    """

    if not value:
        value = "inconnu"

    value = str(value).strip()

    # Suppression des accents
    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    # Minuscules
    value = value.lower()

    # Remplacement des caractères non alphanumériques
    cleaned = []

    for char in value:

        if char.isalnum():
            cleaned.append(char)

        else:
            cleaned.append("_")

    value = "".join(cleaned)

    # Suppression des "_" multiples
    while "__" in value:
        value = value.replace("__", "_")

    # Suppression des "_" au début/à la fin
    value = value.strip("_")

    if not value:
        value = "inconnu"

    return f"{prefix}{value}"


# ============================================================
# CONFIGURATION MYSQL
# ============================================================

def get_db_config():
    """
    Construit la configuration MySQL à partir
    des variables du Credential AWX.
    """

    try:

        return {
            "host": env_or_fail(
                "MYSQL_HOST",
                required=True
            ),

            "port": int(
                env_or_fail(
                    "MYSQL_PORT",
                    "3306"
                )
            ),

            "user": env_or_fail(
                "MYSQL_USER",
                required=True
            ),

            "password": env_or_fail(
                "MYSQL_PASSWORD",
                required=True
            ),

            "database": env_or_fail(
                "MYSQL_DB",
                required=True
            ),

            "connection_timeout": 10,
        }

    except RuntimeError as err:

        log.error(
            "Configuration de la base de donnees incomplete : %s",
            err
        )

        print(
            json.dumps(
                {"error": str(err)},
                ensure_ascii=False
            )
        )

        sys.exit(1)


# ============================================================
# CONNEXION MYSQL
# ============================================================

def get_connection():
    """
    Établit la connexion avec MySQL.
    """

    try:

        debug_environment()

        config = get_db_config()

        print(
            f"CONFIG: host={config['host']} "
            f"port={config['port']} "
            f"db={config['database']} "
            f"user={config['user']}",
            file=sys.stderr
        )

        log.info(
            "Tentative connexion MySQL host=%s port=%s db=%s user=%s",
            config["host"],
            config["port"],
            config["database"],
            config["user"],
        )

        conn = mysql.connector.connect(**config)

        log.info(
            "Connexion MySQL etablie vers %s/%s",
            config["host"],
            config["database"],
        )

        return conn

    except Exception as exc:

        import traceback

        print(
            "\n=== MYSQL CONNECTION ERROR ===",
            file=sys.stderr
        )

        traceback.print_exc(
            file=sys.stderr
        )

        print(
            "================================\n",
            file=sys.stderr
        )

        log.error(
            "Connexion MySQL echouee: %s",
            exc
        )

        print(
            json.dumps(
                {"error": str(exc)},
                ensure_ascii=False
            )
        )

        sys.exit(1)


# ============================================================
# RECUPERATION DES EQUIPEMENTS
# ============================================================

def get_devices(conn):
    """
    Récupère TOUS les équipements présents dans la table devices.

    Important :
    Aucun filtre sur le status n'est appliqué ici.

    Ainsi :

        Production
        Déconnecté
        Maintenance
        etc.

    restent tous visibles dans AWX.
    """

    cursor = None

    try:

        cursor = conn.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT
                id,
                hostname,
                ip_address,
                vendor,
                role,
                status
            FROM devices
            ORDER BY hostname
            """
        )

        devices = cursor.fetchall()

        log.info(
            "%d equipement(s) recupere(s) depuis MySQL",
            len(devices)
        )

        return devices

    except Exception as exc:

        log.error(
            "Erreur lors de la recuperation des equipements : %s",
            exc
        )

        raise

    finally:

        if cursor is not None:
            cursor.close()


# ============================================================
# CONSTRUCTION DE L'INVENTAIRE AWX
# ============================================================

def build_inventory():
    """
    Génère l'inventaire dynamique AWX.

    Organisation :

        all
        |
        +-- status_production
        +-- status_deconnecte
        +-- status_maintenance
        |
        +-- vendor_aruba
        +-- vendor_hpe
        +-- vendor_efficientip
        |
        +-- role_server
        +-- role_switch_distribution
        +-- role_switch_acces

    Tous les équipements sont présents dans "all".
    """

    inventory = {
        "_meta": {
            "hostvars": {}
        },

        "all": {
            "hosts": [],
            "children": []
        }
    }

    conn = get_connection()

    try:

        devices = get_devices(conn)

        # ----------------------------------------------------
        # TRAITEMENT DES EQUIPEMENTS
        # ----------------------------------------------------

        for device in devices:

            hostname = device.get("hostname")

            if not hostname:
                log.warning(
                    "Equipement ignore : hostname vide. ID=%s",
                    device.get("id")
                )
                continue

            hostname = hostname.strip()

            ip_address = device.get("ip_address")
            vendor = device.get("vendor")
            role = device.get("role")
            status = device.get("status")

            # Valeurs par défaut
            vendor_display = (
                vendor.strip()
                if vendor
                else "Inconnu"
            )

            role_display = (
                role.strip()
                if role
                else "Inconnu"
            )

            status_display = (
                status.strip()
                if status
                else "Inconnu"
            )

            # ------------------------------------------------
            # AJOUT DANS ALL
            # ------------------------------------------------

            if hostname not in inventory["all"]["hosts"]:

                inventory["all"]["hosts"].append(
                    hostname
                )

            # ------------------------------------------------
            # GROUPES VENDOR
            # ------------------------------------------------

            vendor_group = normalize_group_name(
                vendor_display,
                prefix="vendor_"
            )

            if vendor_group not in inventory:

                inventory[vendor_group] = {
                    "hosts": [],
                    "vars": {}
                }

                inventory["all"]["children"].append(
                    vendor_group
                )

            if hostname not in inventory[vendor_group]["hosts"]:

                inventory[vendor_group]["hosts"].append(
                    hostname
                )

            # ------------------------------------------------
            # GROUPES ROLE
            # ------------------------------------------------

            role_group = normalize_group_name(
                role_display,
                prefix="role_"
            )

            if role_group not in inventory:

                inventory[role_group] = {
                    "hosts": [],
                    "vars": {}
                }

                inventory["all"]["children"].append(
                    role_group
                )

            if hostname not in inventory[role_group]["hosts"]:

                inventory[role_group]["hosts"].append(
                    hostname
                )

            # ------------------------------------------------
            # GROUPES STATUS
            # ------------------------------------------------

            status_group = normalize_group_name(
                status_display,
                prefix="status_"
            )

            if status_group not in inventory:

                inventory[status_group] = {
                    "hosts": [],
                    "vars": {}
                }

                inventory["all"]["children"].append(
                    status_group
                )

            if hostname not in inventory[status_group]["hosts"]:

                inventory[status_group]["hosts"].append(
                    hostname
                )

            # ------------------------------------------------
            # VARIABLES HOST
            # ------------------------------------------------

            hostvars = {
                "ansible_host": ip_address,

                "device_id": device.get("id"),

                "device_vendor": vendor,

                "device_role": role,

                "device_status": status,
            }

            inventory["_meta"]["hostvars"][hostname] = hostvars

            log.debug(
                "Equipement ajoute : %s | IP=%s | Vendor=%s | Role=%s | Status=%s",
                hostname,
                ip_address,
                vendor_display,
                role_display,
                status_display,
            )

        return inventory

    except Exception as exc:

        log.error(
            "Erreur SQL ou construction inventaire : %s",
            exc
        )

        print(
            json.dumps(
                {"error": str(exc)},
                ensure_ascii=False
            )
        )

        sys.exit(1)

    finally:

        conn.close()

        log.info(
            "Connexion MySQL fermee"
        )


# ============================================================
# VARIABLES D'UN HOST
# ============================================================

def get_host_vars(hostname):
    """
    Retourne les variables d'un équipement.

    Important :
    Aucun filtre sur le status.

    Un équipement Déconnecté ou Maintenance
    reste donc accessible avec --host.
    """

    conn = get_connection()

    cursor = None

    try:

        cursor = conn.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT
                id,
                hostname,
                ip_address,
                vendor,
                role,
                status
            FROM devices
            WHERE hostname = %s
            """,
            (hostname,),
        )

        device = cursor.fetchone()

        if not device:

            log.warning(
                "Hote introuvable dans MySQL : %s",
                hostname
            )

            return {}

        return {
            "ansible_host": device.get(
                "ip_address"
            ),

            "device_id": device.get(
                "id"
            ),

            "device_vendor": device.get(
                "vendor"
            ),

            "device_role": device.get(
                "role"
            ),

            "device_status": device.get(
                "status"
            ),
        }

    except Exception as exc:

        log.error(
            "Erreur recuperation variables hote %s : %s",
            hostname,
            exc
        )

        print(
            json.dumps(
                {"error": str(exc)},
                ensure_ascii=False
            )
        )

        sys.exit(1)

    finally:

        if cursor is not None:
            cursor.close()

        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Inventaire dynamique AWX depuis MySQL"
    )

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--list",
        action="store_true",
        help="Affiche l'inventaire complet"
    )

    group.add_argument(
        "--host",
        metavar="HOSTNAME",
        help="Affiche les variables d'un host"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # --list
    # --------------------------------------------------------

    if args.list:

        inventory = build_inventory()

        print(
            json.dumps(
                inventory,
                indent=2,
                ensure_ascii=False
            )
        )

    # --------------------------------------------------------
    # --host
    # --------------------------------------------------------

    else:

        host_vars = get_host_vars(
            args.host
        )

        print(
            json.dumps(
                host_vars,
                indent=2,
                ensure_ascii=False
            )
        )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    main()
