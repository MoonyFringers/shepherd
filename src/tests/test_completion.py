# Copyright (c) 2025 Moony Fringers
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

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import get_default_expanduser_side_effect, values

from shepctl import ShepherdMng

shpd_config = """
{
  "logging": {
    "file": "${log_file}",
    "level": "${log_level}",
    "stdout": "${log_stdout}",
    "format": "${log_format}"
  },
  "shpd_registry": {
    "ftp_server": "${shpd_registry}",
    "ftp_user": "${shpd_registry_ftp_usr}",
    "ftp_psw": "${shpd_registry_ftp_psw}",
    "ftp_shpd_path": "${shpd_registry_ftp_shpd_path}",
    "ftp_env_imgs_path": "${shpd_registry_ftp_imgs_path}"
  },
  "envs_path": "${envs_path}",
  "volumes_path": "${volumes_path}",
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
    "passphrase": "${ca_passphrase}"
  },
  "cert": {
    "country": "${cert_country}",
    "state": "${cert_state}",
    "locality": "${cert_locality}",
    "organization": "${cert_org}",
    "organizational_unit": "${cert_org_unit}",
    "common_name": "${cert_cn}",
    "email": "${cert_email}",
    "subject_alternative_names": []
  },
  "staging_area": {
    "volumes_path": "${staging_area_volumes_path}",
    "images_path": "${staging_area_images_path}"
  },
  "env_templates":[
    {
      "tag": "default",
      "factory": "docker-compose",
      "service_templates": [
        {
          "template": "default",
          "tag": "service-default"
        }
      ],
      "networks": [
        {
          "tag": "shpdnet",
          "name": "envnet",
          "external": true
        }
      ]
    }
  ],
  "service_templates": [
    {
      "tag": "t1",
      "factory": "docker",
      "image": "test-image:latest",
      "labels": [
        "com.example.label1=value1",
        "com.example.label2=value2"
      ],
      "workdir": "/test",
      "volumes": [
          "/home/test/.ssh:/home/test/.ssh",
          "/etc/ssh:/etc/ssh"
      ],
      "ingress": false,
      "empty_env": null,
      "environment": [],
      "ports": [
        "80:80",
        "443:443",
        "8080:8080"
      ],
      "properties": {},
      "networks": [
        "default"
      ],
      "extra_hosts": [
        "host.docker.internal:host-gateway"
      ],
      "subject_alternative_name": null
    },
    {
      "tag": "t2",
      "factory": "docker",
      "image": "test-image:latest",
      "labels": [
        "com.example.label1=value1",
        "com.example.label2=value2"
      ],
      "workdir": "/test",
      "volumes": [
          "/home/test/.ssh:/home/test/.ssh",
          "/etc/ssh:/etc/ssh"
      ],
      "ingress": false,
      "empty_env": null,
      "environment": [],
      "ports": [
        "80:80",
        "443:443",
        "8080:8080"
      ],
      "properties": {},
      "networks": [
        "default"
      ],
      "extra_hosts": [
        "host.docker.internal:host-gateway"
      ],
      "subject_alternative_name": null
    }
  ],
  "envs": [
    {
      "template": "default",
      "factory": "docker-compose",
      "tag": "test-1",
      "services": [
        {
          "template": "t1",
          "factory": "docker",
          "tag": "red",
          "service_class": "foo-class",
          "image": "test-image:latest",
          "labels": [
            "com.example.label1=value1",
            "com.example.label2=value2"
          ],
          "workdir": "/test",
          "volumes": [
              "/home/test/.ssh:/home/test/.ssh",
              "/etc/ssh:/etc/ssh"
          ],
          "ingress": false,
          "empty_env": null,
          "environment": [],
          "ports": [
            "80:80",
            "443:443",
            "8080:8080"
          ],
          "properties": {},
          "networks": [
            "default"
          ],
          "extra_hosts": [
            "host.docker.internal:host-gateway"
          ],
          "subject_alternative_name": null
        },
        {
          "template": "t1",
          "factory": "docker",
          "tag": "white",
          "image": "test-image:latest",
          "labels": [
            "com.example.label1=value1",
            "com.example.label2=value2"
          ],
          "workdir": "/test",
          "volumes": [
              "/home/test/.ssh:/home/test/.ssh",
              "/etc/ssh:/etc/ssh"
          ],
          "ingress": false,
          "empty_env": null,
          "environment": [],
          "ports": [
            "80:80",
            "443:443",
            "8080:8080"
          ],
          "properties": {},
          "networks": [
            "default"
          ],
          "extra_hosts": [
            "host.docker.internal:host-gateway"
          ],
          "subject_alternative_name": null
        }
      ],
      "archived": false,
      "active": true
    },
    {
      "template": "default",
      "factory": "docker-compose",
      "tag": "test-2",
      "services": [
        {
          "template": "t2",
          "factory": "docker",
          "tag": "blue",
          "image": "test-image:latest",
          "labels": [
            "com.example.label1=value1",
            "com.example.label2=value2"
          ],
          "workdir": "/test",
          "volumes": [
              "/home/test/.ssh:/home/test/.ssh",
              "/etc/ssh:/etc/ssh"
          ],
          "ingress": false,
          "empty_env": null,
          "environment": [],
          "ports": [
            "80:80",
            "443:443",
            "8080:8080"
          ],
          "properties": {},
          "networks": [
            "default"
          ],
          "extra_hosts": [
            "host.docker.internal:host-gateway"
          ],
          "subject_alternative_name": null
        }
      ],
      "archived": false,
      "active": false
    }
  ]
}
"""


@pytest.fixture
def temp_home(tmp_path: Path, mocker: MockerFixture) -> Path:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    config_file.write_text(values)

    return temp_home


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.compl
def test_completion_no_args(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions([])
    assert (
        completions == sm.completionMng.CATEGORIES
    ), "Expected categories only"


@pytest.mark.compl
def test_completion_env_commands(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env"])
    assert (
        completions == sm.completionMng.completionEnvMng.COMMANDS_ENV
    ), "Expected env commands only"


@pytest.mark.compl
def test_completion_env_init(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "init"])
    assert (
        completions == sm.configMng.get_environment_template_tags()
    ), "Expected init completion"


@pytest.mark.compl
def test_completion_env_clone(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "clone"])
    assert completions == ["test-1", "test-2"], "Expected clone completion"


@pytest.mark.compl
def test_completion_env_rename(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "rename"])
    assert completions == ["test-1", "test-2"], "Expected rename completion"


@pytest.mark.compl
def test_completion_env_checkout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "checkout"])
    assert completions == [
        "test-2",
    ], "Expected checkout completion"


@pytest.mark.compl
def test_completion_env_delete(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "delete"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected delete completion"


@pytest.mark.compl
def test_completion_env_list(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "list"])
    assert completions == [], "Expected list completion"


@pytest.mark.compl
def test_completion_env_up(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "up"])
    assert completions == [], "Expected up completion"


@pytest.mark.compl
def test_completion_env_halt(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "halt"])
    assert completions == [], "Expected halt completion"


@pytest.mark.compl
def test_completion_env_reload(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "reload"])
    assert completions == [], "Expected reload completion"


@pytest.mark.compl
def test_completion_env_render(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "render"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected render completion"


@pytest.mark.compl
def test_completion_env_status(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "status"])
    assert completions == [], "Expected status completion"


@pytest.mark.compl
def test_completion_env_add_1(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "add"])
    assert (
        completions == sm.configMng.constants.RESOURCE_TYPES
    ), "Expected add-1 completion"


@pytest.mark.compl
def test_completion_env_add_2(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "add", "svc"])
    assert completions == [], "Expected add-2 completion"


@pytest.mark.compl
def test_completion_env_add_3(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["env", "add", "svc", "foo"])
    assert completions == ["t1", "t2"], "Expected add-3 completion"


@pytest.mark.compl
def test_completion_env_add_4(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["env", "add", "svc", "foo", "t1"]
    )
    assert completions == ["foo-class"], "Expected add-4 completion"


@pytest.mark.compl
def test_completion_db_commands(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["db"])
    assert (
        completions == sm.completionMng.completionDbMng.COMMANDS_DB
    ), "Expected db commands only"


@pytest.mark.compl
def test_completion_db_sql_shell(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["db", "sql-shell"])
    assert completions == ["red", "white"], "Expected sql-shell completion"


@pytest.mark.compl
def test_completion_svc_commands(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc"])
    assert (
        completions == sm.completionMng.completionSvcMng.COMMANDS_SVC
    ), "Expected svc commands only"


@pytest.mark.compl
def test_completion_svc_build(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "build"])
    assert completions == ["t1", "t2"], "Expected build completion"


@pytest.mark.compl
def test_completion_svc_up(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "up"])
    assert completions == ["red", "white"], "Expected up completion"


@pytest.mark.compl
def test_completion_svc_halt(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "halt"])
    assert completions == ["red", "white"], "Expected halt completion"


@pytest.mark.compl
def test_completion_svc_reload(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "reload"])
    assert completions == ["red", "white"], "Expected reload completion"


@pytest.mark.compl
def test_completion_svc_render(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "render"])
    assert completions == ["red", "white"], "Expected render completion"


@pytest.mark.compl
def test_completion_svc_stdout(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "stdout"])
    assert completions == ["red", "white"], "Expected stdout completion"


@pytest.mark.compl
def test_completion_svc_shell(
    temp_home: Path,
    runner: CliRunner,
    mocker: MockerFixture,
):
    side_effect = get_default_expanduser_side_effect(temp_home)
    mocker.patch("os.path.expanduser", side_effect=side_effect)
    shpd_path = temp_home / "shpd"
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_json = shpd_path / ".shpd.json"
    shpd_json.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["svc", "shell"])
    assert completions == ["red", "white"], "Expected shell completion"
