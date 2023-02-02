Build command: `pyinstaller --name 'Ci' --windowed --add-data='./poems.json:.' ci.py`

Create .dmg file for distribution: 

`brew install create-dmg`


`mkdir -p dist/dmg`


`cp -r "dist/Ci.app" dist/dmg`


`create-dmg --volname "Ci" --hide-extension "Ci.app" "dist/Ci.dmg" "dist/dmg/"`