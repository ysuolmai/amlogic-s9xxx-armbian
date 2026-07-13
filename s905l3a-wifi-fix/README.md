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
- `e900v22d-rtl8822cs`: SKYWORTH E900V22D/S905L3A, RTL8822CS (`024C:C822`), using a dedicated DTB derived from the E900V22C base with the broken `wifi32k` dependency removed.

Other E900V22 revisions and S905L3A variants are not modified until their PCB and Wi-Fi wiring have been verified. The E900V22D profile must not be used for similarly named S905L3B or S905L3 devices.

Build the verified E900V22D variant with board name `s905l3a-e900v22d`. The image builder copies `meson-g12a-s905l3a-e900v22c.dtb` to the dedicated `meson-g12a-s905l3a-e900v22d.dtb`, updates the root model/compatible values, removes the non-probing external clock dependency and disables the unused `wifi32k` node.

## Commands

```bash
s905l3a-wifi-fix diagnose
sudo s905l3a-wifi-fix auto --reboot
s905l3a-wifi-fix verify
sudo s905l3a-wifi-fix rollback
```
