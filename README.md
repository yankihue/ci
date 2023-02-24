# Ci
<img width="1800" alt="Desktop image showing an example generated background" src="https://user-images.githubusercontent.com/61288822/221179105-ad1926fa-40c2-47a2-addf-18e14cc1c4d3.png">

Ci is a wallpaper generator that sets your desktop to a random selection [唐詩三百首 (Three Hundred Tang Poems)](https://en.wikipedia.org/wiki/Three_Hundred_Tang_Poems) every 10 minutes. You can manually trigger a new wallpaper generation using the icon on the menubar.
## Requirements

The project uses [齊伋體 qiji-font](https://github.com/LingDong-/qiji-font). It's required to download the font from the [releases page](https://github.com/LingDong-/qiji-font/releases) before installing and using this application. 

The `qiji-combo` version is recommended. Download `qiji-combo.ttf` and double click to install the font.

## Installation

Build command: 
```bash
pyinstaller Ci.spec
```
Create .dmg file for release/distribution:

1. Install crate-dmg with brew:
   
```bash
brew install create-dmg
```

1. Run the script
   
```
chmod +x builddmg.sh
./builddmg.sh
```

## To do
- Add generative/procedural background image
- Add broader selection of poems including Song era and more
