#!/bin/sh
# Create a folder (named dmg) to prepare our DMG in (if it doesn't already exist).
mkdir -p dist/dmg
# Empty the dmg folder.
rm -r dist/dmg/*
# Copy the app bundle to the dmg folder.
cp -r "dist/Ci.app" dist/dmg
# If the DMG already exists, delete it.
test -f "dist/Ci.dmg" && rm "dist/Ci.dmg"
# create-dmg \
#   --volname "Hello World" \
#   --volicon "Hello World.icns" \
#   --window-pos 200 120 \
#   --window-size 600 300 \
#   --icon-size 100 \
#   --icon "Hello World.app" 175 120 \
#   --hide-extension "Hello World.app" \
#   --app-drop-link 425 120 \
#   "dist/Hello World.dmg" \
#   "dist/dmg/"

create-dmg --app-drop-link 600 185 --volname "Ci" --hide-extension "Ci.app" "dist/Ci.dmg" "dist/dmg/"
