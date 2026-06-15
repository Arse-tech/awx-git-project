#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
try:
    import mysql.connector
except ImportError:
    print(json.dumps({"error": "mysql-connector-python non installe dans l'EE"}))
    sys.exit(1)
log_level = os.environ.get("MYSQL_INVENTORY_LOG_LEVEL", "ERROR").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.ERROR),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

log = logging.getLogger(__name__)
def env_or_fail(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Variable d'environnement requise absente: {name}")
    return value
def get_db_config():
    return {
        "host": env_or_fail("MYSQL_HOST", "localhost"),
        "port": int(env_or_fail("MYSQL_PORT", "3306")),
        "user": env_or_fail("MYSQL_USER", required=True),
        "password": env_or_fail("MYSQL_PASSWORD", required=True),
        "database": env_or_fail("MYSQL_DB", required=True),
        "connection_timeout": 10,
    }
def get_connection():
    try:
        config = get_db_config()
        conn = mysql.connector.connect(**config)
        log.info("Connexion MySQL etablie vers %s/%s", config["host"], config["database"])
        return conn
    except Exception as exc:
        log.error("Connexion MySQL echouee: %s", exc)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
def build_inventory():
    inventory = {
        "_meta": {"hostvars": {}},
        "all": {"hosts": [], "children": []},
    }
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT hostname, ip_address, vendor, role, status
            FROM devices
            WHERE status = 'Production'
            ORDER BY hostname
            """
        )
        devices = cursor.fetchall()
        for device in devices:
            name = device["hostname"]
            vendor = (device.get("vendor") or "unknown_vendor").strip().replace(" ", "_")
            role = (device.get("role") or "unknown_role").strip().replace(" ", "_")
            if name not in inventory["all"]["hosts"]:
                inventory["all"]["hosts"].append(name)
            if vendor not in inventory:
                inventory[vendor] = {"hosts": [], "vars": {}}
                inventory["all"]["children"].append(vendor)
            if name not in inventory[vendor]["hosts"]:
                inventory[vendor]["hosts"].append(name)
            if role not in inventory:
                inventory[role] = {"hosts": [], "vars": {}}
                inventory["all"]["children"].append(role)
            if name not in inventory[role]["hosts"]:
                inventory[role]["hosts"].append(name)
            inventory["_meta"]["hostvars"][name] = {
                "ansible_host": device["ip_address"],
                "device_vendor": device.get("vendor"),
                "device_role": device.get("role"),
                "device_status": device.get("status"),
            }
        return inventory
    except Exception as exc:
        log.error("Erreur SQL ou construction inventaire: %s", exc)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
        log.info("Connexion MySQL fermee")
def get_host_vars(hostname):
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT hostname, ip_address, vendor, role, status
            FROM devices
            WHERE hostname = %s
              AND status = 'Production'
            """,
            (hostname,),
        )
        device = cursor.fetchone()
        if not device:
            return {}
        return {
            "ansible_host": device["ip_address"],
            "device_vendor": device.get("vendor"),
            "device_role": device.get("role"),
            "device_status": device.get("status"),
        }
    except Exception as exc:
        log.error("Erreur SQL: %s", exc)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
def main():
    parser = argparse.ArgumentParser(description="Inventaire dynamique AWX depuis MySQL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true")
    group.add_argument("--host", metavar="HOSTNAME")
    args = parser.parse_args()
    if args.list:
        print(json.dumps(build_inventory(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(get_host_vars(args.host), indent=2, ensure_ascii=False))
if __name__ == "__main__":
    main()
