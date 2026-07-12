#!/usr/bin/env bash

set -u

section() {
    printf '\n===== %s =====\n' "$1"
}

run_optional() {
    if command -v "$1" >/dev/null 2>&1; then
        "$@" 2>&1
    else
        printf '%s is not installed\n' "$1"
    fi
}

section "System"
uname -a
cat /etc/os-release 2>/dev/null || true
printf 'Model: '
tr -d '\000' </proc/device-tree/model 2>/dev/null || printf 'unknown'
printf '\n'

section "Boot configuration"
cat /proc/cmdline 2>/dev/null || true
for file in /boot/uEnv.txt /boot/armbianEnv.txt /boot/extlinux/extlinux.conf; do
    if [[ -f "$file" ]]; then
        printf '\n--- %s ---\n' "$file"
        sed -n '1,200p' "$file"
    fi
done

section "Network interfaces"
ip -br link 2>&1

section "RFKill"
run_optional rfkill list

section "MMC devices"
find /sys/bus/mmc/devices -maxdepth 1 -mindepth 1 -printf '%f -> %l\n' 2>/dev/null || true
for file in /sys/bus/mmc/devices/mmc*/uevent; do
    if [[ -f "$file" ]]; then
        printf '\n--- %s ---\n' "$file"
        cat "$file"
    fi
done

section "Relevant modules"
lsmod | grep -Ei 'rtw|rtl|brcm|cfg80211|mac80211|wlan' || true

section "Available wireless module files"
find "/lib/modules/$(uname -r)" -type f 2>/dev/null \
    | grep -Ei 'rtw|rtl|brcm|8822|8723|wlan' \
    | sort || true

section "Platform MMC controllers"
find /sys/bus/platform/devices -maxdepth 1 -name '*mmc*' -printf '%f -> %l\n' 2>/dev/null || true

section "Kernel log"
dmesg 2>&1 | grep -Ei 'mmc|sdio|wifi|wlan|rtw|rtl|brcm|firmware|pwrseq|rfkill' || true

section "Wi-Fi scan"
if command -v nmcli >/dev/null 2>&1; then
    nmcli -f DEVICE,TYPE,STATE,CONNECTION device status 2>&1
    nmcli -f IN-USE,SSID,SIGNAL,SECURITY device wifi list --rescan yes 2>&1 || true
else
    printf 'nmcli is not installed\n'
fi
