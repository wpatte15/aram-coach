# Bundled data

`mayhem_augments.lua` is a copy of the League of Legends Wiki page
[Module:MayhemAugmentData/data](https://wiki.leagueoflegends.com/en-us/Module:MayhemAugmentData/data),
saved on 2026-11-09 during patch 16.22. It lists every ARAM: Mayhem augment with its tier and description.
The text is the work of the wiki's contributors and is used under the wiki's content licence.

The coach downloads a fresh copy when it can. The wiki often refuses automated downloads, and this copy is the
fallback, so augment descriptions can be a patch or more behind.

To refresh it by hand, open this address in a browser, save the page as text, and put it at
`cache/<patch>/mayhem_augments.lua`:

```
https://wiki.leagueoflegends.com/en-us/Module:MayhemAugmentData/data?action=raw
```
