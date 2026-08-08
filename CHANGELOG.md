# Changelog

All notable changes to this project will be documented in this file.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - Unreleased

### Added

- Plugin `config` values are now available to `${VAR}` template
  resolution in that plugin's `service_templates`/`env_templates`, no
  longer requiring a separately-exported, identically-named shell
  variable (#278).
