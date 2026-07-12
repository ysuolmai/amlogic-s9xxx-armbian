# S905L3A SDIO Wi-Fi Fix

This directory contains a profile-driven S905L3A Wi-Fi repair system.

It is deliberately limited to the image builder's `SOC=s905l3a`. A profile is board-specific; the tool never guesses reset GPIO, regulator or clock values.

## One-line repair

On an installed image containing this tool:

```bash
sudo s905l3a-wifi-fix auto --reboot
```

The command detects the active DTB, matches a tested profile, builds and validates a candidate DTB, creates a timestamped backup, installs it atomically and reboots. Unsupported models exit without modifying `/boot`.

## Image integration

During image creation, `rebuild` calls `bin/patch-image` after extracting the kernel DTBs. For a supported S905L3A board this patches the DTB before the image is released, so Wi-Fi should work on the first boot.

The rootfs also contains `s905l3a-wifi-fix.service` as a fallback. It only ships in S905L3A images. If a future kernel DTB arrives unpatched but still matches a tested topology, the service applies the profile and performs one reboot.

## Current profiles

- `m401a-rtl8822cs`: M401A, RTL8822CS, SDIO-A, GPIOX_7 active-low reset.

CM311, E900V22 and other S905L3A variants are not modified until their PCB and Wi-Fi wiring have been verified.

## Commands

```bash
s905l3a-wifi-fix diagnose
sudo s905l3a-wifi-fix auto --reboot
s905l3a-wifi-fix verify
sudo s905l3a-wifi-fix rollback
```
