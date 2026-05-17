# fish completion for kb2xb
# /usr/share/fish/vendor_completions.d/kb2xb.fish

# Helper: list profile IDs from ~/.config/kb2xb/profiles/
function __kb2xb_profiles
    set -l dir "$HOME/.config/kb2xb/profiles"
    if test -d $dir
        for f in $dir/*.json
            basename $f .json
        end
    end
end

# Helper: list /dev/input/event* devices
function __kb2xb_keyboards
    ls /dev/input/event* 2>/dev/null
end

# Conditions
function __kb2xb_no_subcommand
    not __fish_seen_subcommand_from profile keys version
end

function __kb2xb_using_profile
    __fish_seen_subcommand_from profile
end

function __kb2xb_profile_no_subcmd
    __fish_seen_subcommand_from profile
    and not __fish_seen_subcommand_from list create edit show delete
end

# ── Global options ────────────────────────────────────────────────────────────
complete -c kb2xb -n __kb2xb_no_subcommand -s p -l profile \
    -xa '(__kb2xb_profiles)' -d 'Profile ID to load'

complete -c kb2xb -n __kb2xb_no_subcommand -s k -l keyboard \
    -xa '(__kb2xb_keyboards)' -d 'Force a specific keyboard device'

complete -c kb2xb -s v -l verbose -d 'Enable debug logging'
complete -c kb2xb -s V -l version -d 'Print version and exit'

# ── Top-level subcommands ─────────────────────────────────────────────────────
complete -c kb2xb -n __kb2xb_no_subcommand -f \
    -a profile  -d 'Manage game profiles'
complete -c kb2xb -n __kb2xb_no_subcommand -f \
    -a keys     -d 'List all valid key names'
complete -c kb2xb -n __kb2xb_no_subcommand -f \
    -a version  -d 'Print version and exit'

# ── profile subcommands ───────────────────────────────────────────────────────
complete -c kb2xb -n __kb2xb_profile_no_subcmd -f \
    -a list   -d 'List all profiles'
complete -c kb2xb -n __kb2xb_profile_no_subcmd -f \
    -a create -d 'Create a new profile'
complete -c kb2xb -n __kb2xb_profile_no_subcmd -f \
    -a edit   -d 'Open profile JSON in $EDITOR'
complete -c kb2xb -n __kb2xb_profile_no_subcmd -f \
    -a show   -d 'Print profile JSON to stdout'
complete -c kb2xb -n __kb2xb_profile_no_subcmd -f \
    -a delete -d 'Permanently delete a profile'

# profile create --clone <id>
complete -c kb2xb \
    -n '__fish_seen_subcommand_from profile; and __fish_seen_subcommand_from create' \
    -l clone -xa '(__kb2xb_profiles)' -d 'Clone keybindings from profile'

# profile edit / show / delete  → complete profile name
for __subcmd in edit show delete
    complete -c kb2xb \
        -n "__fish_seen_subcommand_from profile; and __fish_seen_subcommand_from $__subcmd" \
        -f -xa '(__kb2xb_profiles)'
end
