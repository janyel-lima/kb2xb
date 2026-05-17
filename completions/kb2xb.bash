# bash completion for kb2xb
# /usr/share/bash-completion/completions/kb2xb

_kb2xb_profiles() {
    local profile_dir="$HOME/.config/kb2xb/profiles"
    if [[ -d "$profile_dir" ]]; then
        find "$profile_dir" -maxdepth 1 -name '*.json' \
            -exec basename {} .json \;
    fi
}

_kb2xb_keyboards() {
    find /dev/input -maxdepth 1 -name 'event*' 2>/dev/null
}

_kb2xb() {
    local cur prev words cword
    _init_completion || return

    local global_opts="--profile -p --keyboard -k --verbose -v --version -V --help -h"
    local commands="profile keys version"
    local profile_cmds="list create edit show delete"

    case "${words[1]}" in
        profile)
            case "${words[2]}" in
                create)
                    case "$prev" in
                        --clone) COMPREPLY=( $(compgen -W "$(_kb2xb_profiles)" -- "$cur") ); return ;;
                        *)
                            if [[ "$cur" == -* ]]; then
                                COMPREPLY=( $(compgen -W "--clone" -- "$cur") )
                            else
                                COMPREPLY=( $(compgen -W "$(_kb2xb_profiles)" -- "$cur") )
                            fi
                            return ;;
                    esac
                    ;;
                edit|show|delete)
                    COMPREPLY=( $(compgen -W "$(_kb2xb_profiles)" -- "$cur") )
                    return ;;
                list)
                    return ;;
                *)
                    COMPREPLY=( $(compgen -W "$profile_cmds" -- "$cur") )
                    return ;;
            esac
            ;;
        keys|version)
            return ;;
        *)
            case "$prev" in
                --profile|-p)
                    COMPREPLY=( $(compgen -W "$(_kb2xb_profiles)" -- "$cur") )
                    return ;;
                --keyboard|-k)
                    COMPREPLY=( $(compgen -W "$(_kb2xb_keyboards)" -- "$cur") )
                    return ;;
            esac

            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$global_opts" -- "$cur") )
            else
                COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
            fi
            ;;
    esac
}

complete -F _kb2xb kb2xb
