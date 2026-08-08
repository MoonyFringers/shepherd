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
- `PluginConfigView.set_plugin_config_value` lets a plugin persist a
  value into its own config block (e.g. from an interactive setup
  command) without requiring the user to hand-edit `~/.shpd.conf`
  (#280).
- Environment instances can now carry their own `config` block,
  distinct from their plugin's config, overriding it for that
  environment's `${VAR}` template resolution only.
  `PluginConfigView.set_environment_config_value` persists into it
  (#281).
