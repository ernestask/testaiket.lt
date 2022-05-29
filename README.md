# testaiket.lt
## Getting started

### Setting up the database

The [db](db) file contains a script to set up the database, so use it with your favorite RDBMS. If you’re content with defaults (SQLite), then simply run this:

```bash
sqlite3 ket.db < db
```

### Scraping

There are two ways the script can authenticate to the website: cookie and password. If you don’t want to leave the password in your shell history, then using the cookie is preferable. All you need to do is log in with your browser and extract the value of the `CMSSESSID520b200f` cookie and pass it to the script via the `--cookie` option:

```sh
scrape.py --category=B --cookie=<COOKIE>
```

If you don’t care:

```sh
scrape.py --category=B --password=<PASSWORD>
```
