# Copyright (c) 2025 Lunatic Fringers
#
# This file is part of Shepherd Core Stack
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import json
import os
import shutil
import sys
from typing import Any, Dict

from rich.console import Console

from .constants import Constants


class Util:
    console = Console()

    @staticmethod
    def confirm(prompt: str) -> bool:
        while True:
            response = input(f"{prompt} [y/n]: ").strip().lower()
            if response in {"y", "yes"}:
                return True
            elif response in {"n", "no"}:
                return False
            else:
                Util.console.print(
                    "Please answer yes or no. [y/n]", style="yellow"
                )

    @staticmethod
    def create_dir(dir_path: str, desc: str):
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
            Util.print_error_and_die(
                f"[{desc}] Failed to create directory: {dir_path}\nError: {e}"
            )

    @staticmethod
    def copy_dir(src_path: str, dest_path: str):
        try:
            os.makedirs(dest_path, exist_ok=True)
            for item in os.listdir(src_path):
                src_item = os.path.join(src_path, item)
                dest_item = os.path.join(dest_path, item)
                if os.path.isdir(src_item):
                    Util.copy_dir(src_item, dest_item)
                else:
                    os.link(src_item, dest_item)
        except OSError as e:
            Util.print_error_and_die(
                f"""Failed to copy directory:
                {src_path} to {dest_path}\nError: {e}"""
            )

    @staticmethod
    def move_dir(src_path: str, dest_path: str):
        try:
            os.rename(src_path, dest_path)
        except OSError as e:
            Util.print_error_and_die(
                f"""Failed to move directory:
                {src_path} to {dest_path}\nError: {e}"""
            )

    @staticmethod
    def remove_dir(dir_path: str):
        try:
            shutil.rmtree(dir_path)
        except OSError as e:
            Util.print_error_and_die(
                f"Failed to remove directory: {dir_path}\nError: {e}"
            )

    @staticmethod
    def print_error_and_die(message: str):
        Util.console.print(f"[bold red]ERROR[/bold red]: {message}")
        sys.exit(1)

    @staticmethod
    def print(message: str):
        Util.console.print(f"{message}", highlight=False)

    @staticmethod
    def ensure_dirs(constants: Constants):
        dirs = {
            "SHPD_ENVS_DIR": constants.SHPD_ENVS_DIR,
            "SHPD_ENV_IMGS_DIR": constants.SHPD_ENV_IMGS_DIR,
            "SHPD_CERTS_DIR": constants.SHPD_CERTS_DIR,
            "SHPD_SSH_DIR": constants.SHPD_SSH_DIR,
            "SHPD_SSHD_DIR": constants.SHPD_SSHD_DIR,
        }

        for desc, dir_path in dirs.items():
            resolved_path = os.path.realpath(dir_path)
            if not os.path.exists(resolved_path) or not os.path.isdir(
                resolved_path
            ):
                Util.create_dir(resolved_path, desc)

    @staticmethod
    def ensure_config_file(constants: Constants):
        config_file_path = constants.SHPD_CONFIG_FILE
        if os.path.exists(config_file_path):
            try:
                with open(config_file_path, "r", encoding="utf-8") as f:
                    json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                Util.print_error_and_die(
                    f"Invalid config file: {config_file_path}\nError: {e}"
                )
            return

        default_config: Dict[Any, Any] = {
            "service_types": [
                {
                    "type": "oracle",
                    "image": "${ora_image}",
                    "empty_env": "${ora_empty_env}",
                    "ingress": False,
                    "envvars": {},
                    "ports": {"net_listener_port": "${ora_listener_port}"},
                    "properties": {
                        "pump_dir_name": "${ora_pump_dir}",
                        "root_db_name": "${ora_root_db_name}",
                        "plug_db_name": "${ora_plug_db_name}",
                        "sys_user": "${db_sys_usr}",
                        "sys_psw": "${db_sys_psw}",
                        "user": "${db_usr}",
                        "psw": "${db_psw}",
                    },
                    "subject_alternative_name": None,
                },
                {
                    "type": "postgres",
                    "image": "${pg_image}",
                    "empty_env": "${pg_empty_env}",
                    "ingress": False,
                    "envvars": {},
                    "ports": {"net_listener_port": "${pg_listener_port}"},
                    "properties": {
                        "sys_user": "${db_sys_usr}",
                        "sys_psw": "${db_sys_psw}",
                        "user": "${db_usr}",
                        "psw": "${db_psw}",
                    },
                    "subject_alternative_name": None,
                },
            ],
            "shpd_registry": {
                "ftp_server": "${shpd_registry}",
                "ftp_user": "${shpd_registry_ftp_usr}",
                "ftp_psw": "${shpd_registry_ftp_psw}",
                "ftp_shpd_path": "${shpd_registry_ftp_shpd_path}",
                "ftp_env_imgs_path": "${shpd_registry_ftp_imgs_path}",
            },
            "host_inet_ip": "${host_inet_ip}",
            "domain": "${domain}",
            "dns_type": "${dns_type}",
            "ca": {
                "country": "${ca_country}",
                "state": "${ca_state}",
                "locality": "${ca_locality}",
                "organization": "${ca_org}",
                "organizational_unit": "${ca_org_unit}",
                "common_name": "${ca_cn}",
                "email": "${ca_email}",
                "passphrase": "${ca_passphrase}",
            },
            "cert": {
                "country": "${cert_country}",
                "state": "${cert_state}",
                "locality": "${cert_locality}",
                "organization": "${cert_org}",
                "organizational_unit": "${cert_org_unit}",
                "common_name": "${cert_cn}",
                "email": "${cert_email}",
                "subject_alternative_names": [],
            },
            "envs": [],
        }
        try:
            with open(config_file_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
        except OSError as e:
            Util.print_error_and_die(
                f"Failed to create config file: {config_file_path}\nError: {e}"
            )
