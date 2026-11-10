# Bundled data

`mayhem_augments.lua` is a copy of the League of Legends Wiki page
[Module:MayhemAugmentData/data](https://wiki.leagueoflegends.com/en-us/Module:MayhemAugmentData/data),
saved on 2026-11-09 during patch 16.22. It lists every ARAM: Mayhem augment with its tier and description.

## Licence of this file

This file uses material from the "Module:MayhemAugmentData/data" page on the
[League of Legends Wiki](https://wiki.leagueoflegends.com/) and is licensed under the
[Creative Commons Attribution-ShareAlike 3.0 licence](https://creativecommons.org/licenses/by-sa/3.0/) (CC BY-SA 3.0),
as set out on the wiki's [Copyrights page](https://wiki.leagueoflegends.com/en-us/League_of_Legends_Wiki:Copyrights).
The file is unmodified. If you change it and share the result, the same licence applies to your version.
That licence covers this one file only, not the rest of the project. Game names and terms in it belong to Riot Games.

## Keeping it current

The coach downloads a fresh copy when it can. The wiki often refuses automated downloads, and this copy is the
fallback, so augment descriptions can be a patch or more behind.

To refresh it by hand, open this address in a browser, save the page as text, and put it at
`cache/<patch>/mayhem_augments.lua`:

```
https://wiki.leagueoflegends.com/en-us/Module:MayhemAugmentData/data?action=raw
```
