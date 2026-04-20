#!/bin/bash

# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

_shepctl_completion() {
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"

    tokens=$(shepctl __complete "${COMP_WORDS[@]:1}")
    readarray -t tokens_array <<< "$tokens"
    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to get completions from shepctl" >&2
        return 1
    fi

    COMPREPLY=( $(compgen -W "${tokens_array[*]}" -- "$cur") )
    return 0
}

complete -F _shepctl_completion shepctl
