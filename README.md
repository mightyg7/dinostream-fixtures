# dinostream-fixtures

Daily pipeline that scrapes upcoming soccer fixtures via [soccerdata](https://github.com/probberechts/soccerdata) and publishes `fixtures.json` for the DinoStream macOS app.

- **Schedule:** daily at 06:00 UTC via GitHub Actions
- **Output:** `docs/fixtures.json`, served via GitHub Pages
- **Window:** next 14 days
- **Competitions:** Big-5 European leagues, UCL/UEL/UECL, internationals

See `schema/fixtures.schema.json` for the JSON contract.
