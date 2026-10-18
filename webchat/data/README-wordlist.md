# scowl-en-50.txt

Source: SCOWL (Spell Checker Oriented Word Lists) 2020.12.07, Kevin Atkinson,
https://downloads.sourceforge.net/wordlist/scowl-2020.12.07.tar.gz
(sha256 5587667caa20c4891390c2d42dbb4d5c4c3f41bee77af1457ece3ba23fb859cc).

Built from `final/english-words.{10,20,35,40,50}` + `final/american-words.{10,20,35,40,50}`,
converted ISO-8859-1 -> UTF-8, lowercased, ASCII a-z only, sorted unique (61,502 words).
SCOWL includes inflected forms (plurals, -ed, -ing).

Licence: permissive SCOWL licence (MIT-like; see SCOWL-COPYRIGHT.txt, which must
accompany copies). Used by webchat/reminders.py for the "confirm when unsure"
instant-save gate; the product never reads /usr/share/dict.
