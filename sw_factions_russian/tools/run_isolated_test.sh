#!/bin/sh
set -eu

game_dir="/home/whs31/.local/share/Steam/steamapps/common/Stellaris"
data_dir="/home/whs31/.local/share/Paradox Interactive/Stellaris"
test_config="$game_dir/steam_settings/mods/sw_factions_russian/tools/test_dlc_load.json"
backup="/tmp/stellaris_dlc_load_before_sw_ru_test.json"

cp "$data_dir/dlc_load.json" "$backup"
restore_config() {
    cp "$backup" "$data_dir/dlc_load.json"
}
trap restore_config EXIT INT TERM

cp "$test_config" "$data_dir/dlc_load.json"
cd "$game_dir"
timeout 90s ./stellaris -nolauncher -batchmode -gdpr-compliant || status=$?

case "${status:-0}" in
    0|124|143) ;;
    *) exit "$status" ;;
esac
