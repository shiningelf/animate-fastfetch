# Nezuko Fastfetch Layout

A custom Fastfetch layout featuring a transparent Nezuko portrait, Japanese quote, system and hardware panels, live wireless/wired network details, and a Demon Slayer footer mark beside an ASCII `NEZUKO` wordmark.

## Requirements

- Fastfetch **2.69 or newer**. This theme was tested with Fastfetch 2.69.0; version 2.71 or newer is not required.
- Python 3
- A Nerd Font for the icons
- A terminal with Kitty graphics support for the PNG images (tested with Ghostty and Konsole)
- NetworkManager (`nmcli`) and `ip` for live network details

## Install

```sh
mkdir -p ~/.config/fastfetch
cp config.jsonc ~/.config/fastfetch/nezuko-layout.jsonc
cp data.jsonc nezuko-panel.py kimetsunoyaiba-footer.png ~/.config/fastfetch/
cp -n nezuko-transparent.png ~/.config/fastfetch/nezuko-transparent.png
fastfetch --config ~/.config/fastfetch/nezuko-layout.jsonc --show-errors
```

The `cp -n` command keeps an existing portrait file. The theme uses a dedicated config file and does not replace Fastfetch's default config.

To use this layout when zsh starts, add this line to `~/.zshrc`:

```sh
fastfetch --config ~/.config/fastfetch/nezuko-layout.jsonc
```

## Layout

The left side shows the transparent portrait. The right side contains the Japanese quote, system and hardware cards, and a network panel. The system card is 36 columns wide, the hardware card is 42 columns wide, and the quote and network panels are 80 columns wide.

The system icon switches between Manjaro and Arch branding based on Fastfetch's OS data. GPU rows are generated from the detected devices. The network panel shows the Wi-Fi name beside the Wireless heading, plus interface addresses and routers for Wireless and Wired connections; public IP is omitted.

The bottom has a small Demon Slayer PNG and a five-row `NEZUKO` wordmark made from terminal text. The footer image uses Kitty graphics at 6 columns by 3 rows. Memory and disk values are shown without usage bars.
