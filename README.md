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
