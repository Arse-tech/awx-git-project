#!/usr/bin/env python3
import sys
import json
import subprocess

# --- ÉTAPE DE DIAGNOSTIC ET AUTO-INSTALL ---
try:
    import mysql.connector
except ImportError:
    # On tente d'installer la bibliothèque si elle manque dans le conteneur AWX
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mysql-connector-python"])
        import mysql.connector
    except Exception as e:
        print(f"ERREUR : Impossible d'installer mysql-connector-python : {e}", file=sys.stderr)
        sys.exit(1)

import logging
# Le reste de ton script (get_inventory, etc.) continue ici...
    
def get_inventory():
    # 1. Connexion à ta base MySQL sur la VM 2
    db_config = {
        'host': '172.16.23.161',
        'user': 'awx_lecteur',
        'password': 'PassAWX_789!',
        'database': 'lab_inventory'
    }

    # Structure de base demandée par Ansible
    inventory = {
        '_meta': {'hostvars': {}},
        'all': {'hosts': []}
    }

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 2. On récupère les machines en production
        cursor.execute("SELECT hostname, ip_address, vendor, role FROM devices WHERE status = 'Production'")
        devices = cursor.fetchall()

        for device in devices:
            name = device['hostname']
            vendor = device['vendor'].replace(' ', '_')
            role = device['role'].replace(' ', '_')

            # 3. On ajoute la machine à la liste globale
            inventory['all']['hosts'].append(name)

            # 4. On crée des groupes automatiques (ex: un groupe "Cisco", un groupe "Server")
            for group in [vendor, role]:
                if group not in inventory:
                    inventory[group] = {'hosts': []}
                inventory[group]['hosts'].append(name)

            # 5. On passe les variables à Ansible (IP, Constructeur, etc.)
            inventory['_meta']['hostvars'][name] = {
                'ansible_host': device['ip_address'],
                'device_vendor': device['vendor'],
                'device_role': device['role']
            }

        conn.close()
    except Exception as e:
        return {"error": str(e)}

    return inventory

# Ansible appelle toujours le script avec l'option --list
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        print(json.dumps(get_inventory(), indent=2))
    else:
        # Si on l'appelle sans argument, on renvoie une structure vide propre
        print(json.dumps({'_meta': {'hostvars': {}}}, indent=2))
