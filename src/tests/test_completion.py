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

import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture
from test_util import values

from shepctl import ShepherdMng

shpd_config = """
shpd_registry:
  ftp_server: ${shpd_registry}
  ftp_user: ${shpd_registry_ftp_usr}
  ftp_psw: ${shpd_registry_ftp_psw}
  ftp_shpd_path: ${shpd_registry_ftp_shpd_path}
  ftp_env_imgs_path: ${shpd_registry_ftp_imgs_path}
templates_path: ${templates_path}
envs_path: ${envs_path}
volumes_path: ${volumes_path}
host_inet_ip: ${host_inet_ip}
domain: ${domain}
dns_type: ${dns_type}
ca:
  country: ${ca_country}
  state: ${ca_state}
  locality: ${ca_locality}
  organization: ${ca_org}
  organizational_unit: ${ca_org_unit}
  common_name: ${ca_cn}
  email: ${ca_email}
  passphrase: ${ca_passphrase}
cert:
  country: ${cert_country}
  state: ${cert_state}
  locality: ${cert_locality}
  organization: ${cert_org}
  organizational_unit: ${cert_org_unit}
  common_name: ${cert_cn}
  email: ${cert_email}
  subject_alternative_names: []
staging_area:
  volumes_path: ${staging_area_volumes_path}
  images_path: ${staging_area_images_path}
env_templates:
  - tag: default
    factory: docker-compose
    service_templates:
      - template: default
        tag: service-default
    networks:
      - tag: shpdnet
        name: envnet
        external: true
service_templates:
  - tag: t1
    factory: docker
    containers:
      - image: test-image:latest
        tag: container-1
        workdir: /test
        environment: []
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        networks:
          - default
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
    labels:
      - com.example.label1=value1
      - com.example.label2=value2
    ingress: false
    empty_env: null
    properties: {}
  - tag: t2
    factory: docker
    containers:
      - image: test-image:latest
        tag: container-2
        workdir: /test
        environment: []
        volumes:
          - /home/test/.ssh:/home/test/.ssh
          - /etc/ssh:/etc/ssh
        ports:
          - 80:80
          - 443:443
          - 8080:8080
        networks:
          - default
        extra_hosts:
          - host.docker.internal:host-gateway
        subject_alternative_name: null
    labels:
      - com.example.label1=value1
      - com.example.label2=value2
    ingress: false
    empty_env: null
    properties: {}
envs:
  - template: default
    factory: docker-compose
    tag: test-1
    services:
      - template: t1
        factory: docker
        tag: red
        service_class: foo-class
        containers:
          - image: test-image:latest
            tag: container-1
            workdir: /test
            environment: []
            volumes:
              - /home/test/.ssh:/home/test/.ssh
              - /etc/ssh:/etc/ssh
            ports:
              - 80:80
              - 443:443
              - 8080:8080
            networks:
              - default
            extra_hosts:
              - host.docker.internal:host-gateway
            subject_alternative_name: null
        labels:
          - com.example.label1=value1
          - com.example.label2=value2
        ingress: false
        empty_env: null
        properties: {}
        status:
          active: true
          archived: false
          triggered_config: null
      - template: t1
        factory: docker
        tag: white
        containers:
          - image: test-image:latest
            tag: container-1
            workdir: /test
            environment: []
            volumes:
              - /home/test/.ssh:/home/test/.ssh
              - /etc/ssh:/etc/ssh
            ports:
              - 80:80
              - 443:443
              - 8080:8080
            networks:
              - default
            extra_hosts:
              - host.docker.internal:host-gateway
            subject_alternative_name: null
        ingress: false
        status:
          active: true
          archived: false
          triggered_config: null
    status:
      active: true
      archived: false
      triggered_config: null
  - template: default
    factory: docker-compose
    tag: test-2
    services:
      - template: t2
        factory: docker
        tag: blue
        containers:
          - image: test-image:latest
            tag: container-2
            workdir: /test
            environment: []
            volumes:
              - /home/test/.ssh:/home/test/.ssh
              - /etc/ssh:/etc/ssh
            ports:
              - 80:80
              - 443:443
              - 8080:8080
            networks:
              - default
            extra_hosts:
              - host.docker.internal:host-gateway
            subject_alternative_name: null
        ingress: false
        status:
          active: true
          archived: false
          triggered_config: null
    status:
      active: false
      archived: false
      triggered_config: null
"""


@pytest.fixture
def shpd_conf(tmp_path: Path, mocker: MockerFixture) -> tuple[Path, Path]:
    """Fixture to create a temporary home directory and .shpd.conf file."""
    temp_home = tmp_path / "home"
    temp_home.mkdir()

    config_file = temp_home / ".shpd.conf"
    config_file.write_text(values.replace("${test_path}", str(temp_home)))

    os.environ["SHPD_CONF"] = str(config_file)
    return temp_home, config_file


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.compl
def test_completion_no_args(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    sm = ShepherdMng()
    completions = sm.completionMng.get_completions([])
    assert (
        completions == sm.completionMng.VERBS
    ), "Expected Verbs and Shortcuts only"


@pytest.mark.compl
def test_completion_add(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["add"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["add"]
    ), "Expected add completion"


@pytest.mark.compl
def test_completion_add_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["add", "env"])
    assert (
        completions == sm.configMng.get_environment_template_tags()
    ), "Expected add-env completion"


@pytest.mark.compl
def test_completion_add_svc_1(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["add", "svc"])
    assert completions == ["t1", "t2"], "Expected add svc -1- completion"


@pytest.mark.compl
def test_completion_add_svc_2(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["add", "svc", "t1"])
    assert completions == [], "Expected add svc -2- completion"


@pytest.mark.compl
def test_completion_add_svc_3(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(
        ["add", "svc", "t1", "svc-tag"]
    )
    assert completions == ["foo-class"], "Expected add svc -3- completion"


@pytest.mark.compl
def test_completion_clone(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["clone"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["clone"]
    ), "Expected clone completion"


@pytest.mark.compl
def test_completion_clone_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["clone", "env"])
    assert completions == ["test-1", "test-2"], "Expected env clone completion"


@pytest.mark.compl
def test_completion_rename(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["rename"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["rename"]
    ), "Expected rename completion"


@pytest.mark.compl
def test_completion_rename_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["rename", "env"])
    assert completions == ["test-1", "test-2"], "Expected env rename completion"


@pytest.mark.compl
def test_completion_checkout_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["checkout"])
    assert completions == [
        "test-2",
    ], "Expected env checkout completion"


@pytest.mark.compl
def test_completion_delete(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["delete"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["delete"]
    ), "Expected delete completion"


@pytest.mark.compl
def test_completion_delete_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["delete", "env"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected env delete completion"


@pytest.mark.compl
def test_completion_list(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["list"])
    assert completions == [], "Expected list completion"


@pytest.mark.compl
def test_completion_start(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["up"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["up"]
    ), "Expected up completion"


@pytest.mark.compl
def test_completion_start_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["up", "env"])
    assert completions == [], "Expected env up completion"


@pytest.mark.compl
def test_completion_start_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["up", "svc"])
    assert completions == ["red", "white"], "Expected up svc completion"


@pytest.mark.compl
def test_completion_stop(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["halt"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["halt"]
    ), "Expected halt completion"


@pytest.mark.compl
def test_completion_stop_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["halt", "env"])
    assert completions == [], "Expected env halt completion"


@pytest.mark.compl
def test_completion_stop_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["halt", "svc"])
    assert completions == ["red", "white"], "Expected halt svc completion"


@pytest.mark.compl
def test_completion_reload(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["reload"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["reload"]
    ), "Expected reload completion"


@pytest.mark.compl
def test_completion_reload_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["reload", "env"])
    assert completions == [], "Expected env reload completion"


@pytest.mark.compl
def test_completion_reload_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["reload", "svc"])
    assert completions == ["red", "white"], "Expected reload svc completion"


@pytest.mark.compl
def test_completion_get(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["get"])
    assert (
        completions == sm.completionMng.VERB_CATEGORIES["get"]
    ), "Expected get completion"


@pytest.mark.compl
def test_completion_get_env_oyaml(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["get", "env", "-oyaml"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected get env -oyaml completion"


@pytest.mark.compl
def test_completion_get_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["get", "env"])
    assert completions == [
        "test-1",
        "test-2",
    ], "Expected get env completion"


@pytest.mark.compl
def test_completion_get_svc_oyaml(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["get", "svc", "-oyaml"])
    assert completions == ["red", "white"], "Expected get svc -oyaml completion"


@pytest.mark.compl
def test_completion_build_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["build"])
    assert completions == ["red", "white"], "Expected build svc completion"


@pytest.mark.compl
def test_completion_logs_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["logs"])
    assert completions == ["red", "white"], "Expected logs svc completion"


@pytest.mark.compl
def test_completion_shell_svc(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["shell"])
    assert completions == ["red", "white"], "Expected shell svc completion"


@pytest.mark.compl
def test_completion_status_env(
    shpd_conf: tuple[Path, Path],
    runner: CliRunner,
    mocker: MockerFixture,
):
    shpd_path = shpd_conf[0]
    shpd_path.mkdir(parents=True, exist_ok=True)
    shpd_yaml = shpd_path / ".shpd.yaml"
    shpd_yaml.write_text(shpd_config)

    sm = ShepherdMng()
    completions = sm.completionMng.get_completions(["status", "env"])
    assert completions == [], "Expected status env completion"
