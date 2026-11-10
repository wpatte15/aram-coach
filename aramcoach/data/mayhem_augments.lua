-- <pre>
return {
	["ADAPt"] = {
		["description"] = "Convert '''all''' of your {{as|'''bonus''' attack damage}} into {{as|ability power}} at a rate of {{as|1 ability power|ap}} per {{as|{{fd|0.6}} '''bonus''' attack damage|ad}}. Additionally, increase your {{as|ability power by 15%}}.",
		["tier"] = "Silver",
	},
	["Blunt Force"] = {
		["description"] = "Increases {{as|attack damage}} by {{as|20%|AD}}.",
		["tier"] = "Silver",
	},
	["Deft"] = {
		["description"] = "Grants {{as|60% '''bonus''' attack speed}}.",
		["tier"] = "Silver",
	},
	["Dive Bomber"] = {
		["description"] = "Upon death, you explode to deal {{as|true damage}} equal to {{as|20% of the target's '''maximum''' health}} to enemies within 500 units.",
		["tier"] = "Silver",
	},
	["Don't Blink"] = {
		["description"] = "Deal 1% increased damage per {{as|10 movement speed}} you have more than the target.",
		["tier"] = "Silver",
	},
	["Erosion"] = {
		["description"] = "Each instance of damage dealt to an enemy reduces their {{as|armor}} and {{as|magic resistance}} by {{fd|1.5}}% for 4 seconds, stacking up to 20 times for a total of 30% resistances reduction.",
		["tier"] = "Silver",
	},
	["Escape Plan"] = {
		["description"] = "Upon dropping below {{as|35% '''maximum''' health}}, gain a {{tip|shield}} for {{as|65% of your '''maximum''' health}} for {{fd|5.5}} seconds, during which you also gain {{as|150% '''bonus''' movement speed}} and have reduced size (75 second cooldown). The shield and bonus movement speed decay over the duration.",
		["tier"] = "Silver",
		["notes"] = [=[
		* This effect will still trigger if damage is taken while below {{as|35% '''maximum''' health}}.
        ]=]		
	},
	["First-Aid Kit"] = {
		["description"] = "Grants 20% {{stil|heal and shield power}}.",
		["tier"] = "Silver",
	},
	["Flashbang"] = {
		["description"] = "Using {{si|Flash}} creates an explosion around the blink location that deals {{as|{{pp|70 to 240}}|magic damage}} {{as|(+ 70% AD)}} {{as|(+ 60% AP)}} {{as|magic damage}} to nearby enemies and {{tip|slow|slows}} them by 35% for {{fd|1.25}} seconds. Additionally, the cooldown of your {{si|Flash}} resets upon your death.<br><br>''This augment cannot be rolled unless you have the Flashy augment. If {{si|Flash}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Flash}}.''",
		["tier"] = "Silver",
	},
	["Goredrink"] = {
		["description"] = "Gain {{as|15% omnivamp}}.",
		["tier"] = "Silver",
	},
	["Guilty Pleasure"] = {
		["description"] = "{{tip|Immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion {{tip|heal|heals}} you for {{pp|30 to 250}} {{as|(+ {{fd|1.5}}% '''maximum''' health)}} (5 second cooldown per {{tip|cast instance}}).",
		["tier"] = "Silver",
	},
	["Heavy Hitter"] = {
		["description"] = "Basic attacks deal {{as|'''bonus''' physical damage}} equal to {{as|{{fd|3.5}}% of your '''maximum''' health}}.",
		["tier"] = "Silver",
	},
	["Homeguard"] = {
		["description"] = "Gain {{as|100% '''bonus''' movement speed}}. This bonus is lost for 6 seconds after taking damage.",
		["tier"] = "Silver",
	},
	["Ice Cold"] = {
		["description"] = "Your {{tip|slow|slowing}} effects reduce the {{as|movement speed}} of targets by an additional {{as|75|ms}}.",
		["tier"] = "Silver",
	},
	["Infernal Soul"] = {
		["description"] = "Grants the {{bi|Infernal Dragon Soul}}, or a different {{bi|Dragon Soul}} if you aleady have it.",
		["tier"] = "Silver",
	},
	["Leg Day"] = {
		["description"] = "Gain {{as|50 '''bonus''' movement speed}} and 50% {{tip|slow resist}}.",
		["tier"] = "Silver",
	},
	["Light 'em Up!"] = {
		["description"] = "Basic attacks {{tip|on-hit}} generate a stack, up to 4. The fourth stack consumes them all to quickly launch 4 missiles at the target that each deal {{as|{{pp|11 to 80}}|magic damage}} {{as|(+ 35% '''bonus''' AD)}} {{as|(+ 19% AP)}} {{as|'''bonus''' magic damage}} {{tip|on-hit}}, for a total of {{as|{{pp|11*4 to 80*4}}|magic damage}} {{as|(+ {{ap|35*4}}% '''bonus''' AD)}} {{as|(+ {{ap|19*4}}% AP)}}.",
		["tier"] = "Silver",
	},
	["Mountain Soul"] = {
		["description"] = "Grants the {{bi|Mountain Dragon Soul}}, or a different {{bi|Dragon Soul}} if you aleady have it.",--is it modified?
		["tier"] = "Silver",
	},
	["Mighty Shield"] = {
		["description"] = "Gain {{pp|40 to 100}} {{tip|adaptive force}} for 3 seconds upon gaining a {{tip|shield}} (5 second cooldown).",
		["tier"] = "Silver",
	},
	["Mind to Matter"] = {
		["description"] = "Grants {{as|'''bonus''' health}} equal to {{as|50% '''maximum''' mana}}.",
		["tier"] = "Silver",
		["notes"] = [=[
        * Maximum bonus health granted by this effect is capped at {{as|99,999 '''bonus''' health}}.
        ]=]		
	},
	["Ocean Soul"] = {
		["description"] = "Grants the {{bi|Ocean Dragon Soul}}, which has a modified base heal value of 100, or a different {{bi|Dragon Soul}} if you aleady have it.",
		["tier"] = "Silver",
	},
	["Poltergeist"] = {
		["description"] = "Replace a summoner spell with ''{{si|Poltergeist}}''.<br><br>[[File:Poltergeist.png|20px|link=]] {{sbc|Poltergeist:}} {{#invoke:SpellData|geteffect|Poltergeist}}",
		["tier"] = "Silver",
	},	
	["Scoped Weapons"] = {
		["description"] = "Gain {{rd|75|50}} '''bonus''' attack range.",
		["tier"] = "Silver",
	},
	["Shadow Runner"] = {
		["description"] = "After {{tip|dash|dashing}}, {{tip|blink|blinking}}, or exiting {{tip|stealth}}, gain {{as|300 '''bonus''' movement speed}} for 2 seconds.",
		["tier"] = "Silver",
	},
	["Sonic Boom"] = {
		["description"] = "Granting a [[buff]], {{tip|heal}}, or {{tip|shield}} to your ally deals {{as|{{pp|30 to 150}} true damage}} to enemies within 450 units of them and {{tip|slow|slows}} targets by 30% for 2 seconds (2 second cooldown).",
		["tier"] = "Silver",
	},
	["Spin To Win"] = {
		["description"] = "Your {{tt|spinning abilities|Any ability with 'spinning' properties}} deal 30% increased damage and have their cooldown reduced equivalent to 30 ability haste. The damage amplifier is increased to 50% for ultimate abilities.",
		["tier"] = "Silver",
		["notes"] = [=[
		{{Editors needed|This note is not fully complete. If you wish to contribute, please do so on [{{fullurl:{{TALKPAGENAME}}}} Discussion page]|There are a lot of abilities that would not usually spin...|}}
		* {{sbc|Eligible Abilities}}: {{cai|Fox-Fire|Ahri}} and {{ai|Spirit Rush|Ahri}}, {{cai|Tantrum|Amumu}}, {{cai|Lacerate|Ambessa}}, {{cai|Decimate|Darius}}, {{cai|Spinning Axe|Draven}}, {{ai|Stand Aside|Draven}}, and {{ai|Whirling Death|Draven}}, {{cai|Judgment|Garen}}, {{cai|Rampage|Hecarim}}, {{cai|Counter Strike|Jax}}, {{cai|Voracity|Katarina}} and {{ai|Death Lotus|Katarina}}, {{cai|Reaping Slash|Kayn}}, {{cai|Blooming Blows|Lillia}}, {{cai|Eviscerate|Naafiri}}, {{cai|Umbra Blades|Nocturne}}, {{cai|Powerball|Rammus}}, {{cai|Cull the Meek|Renekton}} and {{ai|Slice and Dice|Renekton}}, {{cai|Queen's Wrath|Rek'Sai}}, {{cai|Broken Wings|Riven}}, {{cai|Blade Whirl|Samira}} and {{ai|Inferno Trigger|Samira}}, {{cai|Petricite Burst|Sylas}}, {{cai|Cyclone|Wukong}}, {{cai|Spinning Slash|Tryndamere}}, {{cai|Crescent Guard|Xin Zhao}}, {{cai|Shadow Slash|Zed}}
		* {{Pending for test}}: {{cai|Avengerang|Akshan}} and {{ai|Heroic Swing|Akshan}}, {{cai|Watch Out! Eep!|Lillia}} and {{ai|Swirlseed|Lillia}}, {{cai|Keeper's Verdict|Poppy}}, etc.
		]=]	
	},
	["Swift and Safe"] = {
		["description"] = "After {{tip|dash|dashing}} or {{tip|blink|blinking}}, gain a {{tip|shield}} that lasts for 2 seconds and absorbs {{pp|65 to 290}} {{as|(+ 65% AD)}} {{as|(+ 26% AP)}} damage (5 second cooldown).",
		["tier"] = "Silver",
	},
	["Tank It Or Leave It"] = {
		["description"] = "Gain ''Critical Defend Chance'' equal to {{as|100% critical strike chance}}, up to 50%. Additionally, gain {{as|25% critical strike chance}}.<br><br>{{sbc|Critical Defend Chance:}} Grants you a chance to reduce an instance of damage taken by 20% (5 second cooldown per enemy spell {{tip|cast instance}}).",
		["tier"] = "Silver",
	},
	["Transmute: Gold"] = {
		["description"] = "Gain one random Gold-tier augment.",
		["tier"] = "Silver",
	},
	["Typhoon"] = {
		["description"] = "Basic attacks launch a missile at a nearby enemy, prioritizing champions, that deals {{as|30% AD}} {{as|physical damage}} and applies {{tip|on-hit}} effects.",
		["tier"] = "Silver",
	},
	["Ultimate Unstoppable"] = {
		["description"] = "Casting your ultimate ability grants you {{tip|cc-immune|crowd control immunity}} for 3 seconds (8 second cooldown).",
		["tier"] = "Silver",
	},
	["Upgrade Collector"] = {
		["description"] = "Upgrades {{ii|The Collector}}, empowering {{nie|Death}} to have its execution threshold increased by {{fd|0.5}}% each time you kill an enemy champion, capped at a threshold of {{as|12.5% of the target's '''maximum''' health}}, and {{nie|Taxes}} to generate a further {{g|25}} (total {{g|50}}) from kills. Additionally, gain {{g|250}}.",
		["tier"] = "Silver",
	},
	["Upgrade Immolate"] = {
		["description"] = "Upgrades {{ii|Bami's Cinder}}, {{ii|Hollow Radiance}}, {{ii|Sunfire Aegis}}, and {{ii|Void Immolation}}, empowering {{nie|Immolate}} to additionally grant you {{g|12}} per tick for each enemy champion afflicted by its effect. Additionally, gain {{g|250}}.",
		["tier"] = "Silver",
		["notes"] = [=[
        * {{tip|Clones}} do not count as valid targets for the effect.
        ]=]		
	},
	["Upgrade Zhonya's"] = {
		["description"] = "Upgrades {{ii|Seeker's Armguard}}, {{ii|Wooglet's Witchcap}}, and {{ii|Zhonya's Hourglass}}, empowering {{nie|Stasis}} to {{tip|cleanse}} you of all {{tip|crowd control}} and allow you to move during its active effect, during which time you also gain {{as|50% '''bonus''' movement speed}}. Additionally, the cooldown of {{iis|Zhonya's Hourglass}} Stasis is reduced to 45 seconds.",
		["tier"] = "Silver",
		["notes"] = [=[
        * The active cannot be used while affected by {{tip|cast-inhibiting crowd control}} despite cleansing the user.
        ]=]		
	},
	["Veil of Warding"] = {
		["description"] = "Grants a {{tip|spell shield}} that blocks the next hostile ability (30 second cooldown, timer does '''not''' restart from champion damage taken).",
		["tier"] = "Silver",
	},
	["Witchful Thinking"] = {
		["description"] = "Grants {{as|{{pp|20 to 80}} ability power}}.",
		["tier"] = "Silver",
	},
	["EscAPADe"] = {
		["description"] = "Convert '''all''' of your {{as|ability power}} into {{as|'''bonus''' attack damage}} at a rate of {{as|1 '''bonus''' attack damage|ad}} per {{as|{{fd|1.66}} ability power|ap}}. Additionally, increase your {{as|'''total''' attack damage by 15%}}.",
		["tier"] = "Silver",
	},
	["All For You"] = {
		["description"] = "Your {{tip|heals}} and {{tip|shields}} on allied champions are increased in effectiveness by 30%.",
		["tier"] = "Gold",
	},
	["Apex Inventor"] = {
		["description"] = "Grants {{as|100 item haste|ability haste}}, which is equivalent to 50% cooldown reduction for items.",
		["tier"] = "Gold",
		["notes"] = [=[
{| class="article-table article-table-selected" style="width: 750px;
! rowspan="1" colspan="11" style="width:150px; text-align:center;" | Item Cooldowns
|-{{#vardefine:AIHaste|100}}
! style="text-align:center;" |Items
! style="text-align:center;" |Base Cooldown
! style="text-align:center;" |Reduced Cooldown with [[File:Apex_Inventor_mayhem_augment.png|35px]] Apex Inventor
|-
! style="text-align:center;" | {{ii|Diadem of Songs|icononly=yes}}
| style="text-align:center;" |{{fd|1}} 
| style="text-align:center;" |{{fd|{{#expr:(1-1*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" | {{ii|Sheen|icononly=yes}}{{ii|Iceborn Gauntlet|icononly=yes}}{{ii|Lich Bane|icononly=yes}}{{ii|Trinity Force|icononly=yes}}{{ii|Dusk and Dawn|icononly=yes}}
| style="text-align:center;" |{{fd|1.5}} 
| style="text-align:center;" |{{fd|{{#expr:(1.5-1.5*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" | {{ii|Malignance|icononly=yes}}
| style="text-align:center;" |3
| style="text-align:center;" |{{fd|{{#expr:(3-3*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" | {{ii|Unending Despair|icononly=yes}}
| style="text-align:center;" |4
| style="text-align:center;" |{{#expr:(4-4*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Eclipse|icononly=yes}}
| style="text-align:center;" |6
| style="text-align:center;" |{{#expr:(6-6*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Tear of the Goddess|icononly=true}}{{ii|Archangel's Staff|icononly=yes}}{{ii|Fimbulwinter|icononly=yes}}{{ii|Manamune|icononly=yes}}{{ii|Winter's Approach|icononly=yes}}{{ii|Whispering Circlet|icononly=yes}}
| style="text-align:center;" |8
| style="text-align:center;" |{{#expr:(8-8*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Tiamat|icononly=yes}}{{ii|Profane Hydra|icononly=yes}}{{ii|Ravenous Hydra|icononly=yes}}{{ii|Titanic Hydra|icononly=yes}}{{ii|Sundered Sky|icononly=yes}}
| style="text-align:center;" |10 
| style="text-align:center;" |{{#expr:(10-10*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Luden's Echo|icononly=yes}}
| style="text-align:center;" |12
| style="text-align:center;" |{{#expr:(12-12*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Blade of the Ruined King|icononly=yes}}{{ii|Stridebreaker|icononly=yes}}{{ii|Kaenic Rookern|icononly=yes}}
| style="text-align:center;" |15 
| style="text-align:center;" |{{fd|{{#expr:(15-15*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" | {{ii|Banshee's Veil|icononly=yes}}{{ii|Experimental Hexplate|icononly=yes}}{{ii|Heartsteel|icononly=yes}}{{ii|Horizon Focus|icononly=yes}}{{ii|Stormsurge|icononly=yes}}{{ii|Yun Tal Wildarrows|icononly=yes}}
| style="text-align:center;" |30 
| style="text-align:center;" |{{#expr:(30-30*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Hextech Alternator|icononly=yes}}{{ii|Scout's Slingshot|icononly=yes}}{{ii|Edge of Night|icononly=yes}}{{ii|Hextech Rocketbelt|icononly=yes}}
| style="text-align:center;" |40 
| style="text-align:center;" |{{#expr:(40-40*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Youmuu's Ghostblade|icononly=yes}}{{ii|Zeke's Convergence|icononly=yes}}{{ii|Fiendhunter Bolts|icononly=yes}}{{ii|Lifeline|icononly=yes}}{{ii|Spectral Cutlass|icononly=yes}}
| style="text-align:center;" |45 
| style="text-align:center;" |{{fd|{{#expr:(45-45*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" | {{ii|Verdant Barrier|icononly=yes}}{{ii|Cryptbloom|icononly=yes}}{{ii|Knight's Vow|icononly=yes}}{{ii|Hextech Gunblade|icononly=yes}}{{ii|Actualizer|icononly=yes}}{{ii|Shurelya's Battlesong|icononly=yes}}{{ii|Immortal Shieldbow|icononly=yes}}{{ii|Maw of Malmortius|icononly=yes}}{{ii|Sterak's Gage|icononly=yes}}{{ii|Protoplasm Harness|icononly=yes}}{{ii|Randuin's Omen|icononly=yes}}
| style="text-align:center;" |60 
| style="text-align:center;" |{{#expr:(60-60*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" |{{ii|Hexdrinker|icononly=yes}}{{ii|Locket of the Iron Solari|icononly=yes}}{{ii|Seraph's Embrace|icononly=yes}}
| style="text-align:center;" |75 
| style="text-align:center;" |{{fd|{{#expr:(75-75*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}}}
|-
! style="text-align:center;" |{{ii|Quicksilver Sash|icononly=yes}}{{ii|Mercurial Scimitar|icononly=yes}}{{ii|Redemption|icononly=yes}}
{{ii|Umbral Glaive|icononly=yes}}
| style="text-align:center;" |90
| style="text-align:center;" |{{#expr:(90-90*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
|-
! style="text-align:center;" | {{ii|Mikael's Blessing|icononly=true}}{{ii|Zhonya's Hourglass|icononly=true}}
| style="text-align:center;" |120
| style="text-align:center;" |{{#expr:(120-120*(1-1/(1+({{#var:AIHaste}})/100))) round 2}}
        ]=]		
	},
	["Big Brain"] = {
		["description"] = "Gain a {{tip|shield}} that absorbs damage equal to {{as|300% AP}} and lasts until destroyed. Shield is replenished upon respawn and every 70 seconds.",
		["tier"] = "Gold",
	},
	["Bread And Butter"] = {
		["description"] = "Your champion's first basic ability ''(Q)'' gains {{as|100 ability haste}}.",
		["tier"] = "Gold",
	},
	["Bread And Cheese"] = {
		["description"] = "Your champion's third basic ability ''(E)'' gains {{as|100 ability haste}}.",
		["tier"] = "Gold",
	},
	["Bread And Jam"] = {
		["description"] = "Your champion's second basic ability ''(W)'' gains {{as|100 ability haste}}.",
		["tier"] = "Gold",
	},
	["Celestial Body"] = {
		["description"] = "Gain {{as|1500 '''bonus''' health}}, but reduce your damage output by 10%.",
		["tier"] = "Gold",
	},
	["Critical Healing"] = {
		["description"] = "Your {{tip|heals}} and {{tip|shields}} now have a chance equal to your {{sti|critical strike chance|{{as|critical strike chance}}}} to increase in effectiveness by 40% (5 second cooldown per {{tip|cast instance}}). Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Gold",
	},
	["Critical Rhythm"] = {
		["description"] = "Your {{tip|critical strikes}} grant you {{as|6% '''bonus''' attack speed}} for 6 seconds, stacking up to 10 times for a total of {{as|60%|attack speed}}. Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Gold",
	},
	["Dawnbringer's Resolve"] = {
		["description"] = "Upon dropping below {{as|50% '''maximum''' health}}, you are {{tip|heal|healed}} for{{ft|{{as|30% of your '''maximum''' health}}|{{as|{{ap|30/12}}% of your '''maximum''' health}} every {{fd|0.25}} seconds}}over 3 seconds (45 second cooldown, reset upon death).",
		["tier"] = "Gold",
		["notes"] = [=[
		* This effect will still trigger if damage is taken while below {{as|50% '''maximum''' health}}.
        ]=]		
	},
	["Divine Intervention"] = {
		["description"] = "{{as|Automatically}} cast {{cai|Cosmic Radiance|Taric}}, calling down a protective star upon you that descends over {{fd|2.5}} seconds. Afterwards, you and all allied champions within {{tip|cr|icononly=true}} 400 units become {{tip|invulnerable}} for {{fd|2.5}} seconds (35 second cooldown).",
		["tier"] = "Gold",
	},
	["Ethereal Weapon"] = {
		["description"] = "Your abilities apply {{tip|on-hit}} effects (1 second cooldown per target).",
		["tier"] = "Gold",
	},
	["Firebrand"] = {
		["description"] = "Basic attacks {{tip|on-hit}} apply a {{as|Burn}} for 5 seconds that deals {{as|'''bonus''' magic damage}} equal to{{ft|{{as|{{ap|2/5}}% of the target's '''maximum''' health}} per second.|{{as|2% of the target's '''maximum''' health}} over the duration.}}This {{as|Burn}} stacks infinitely and refreshes with each application.",
		["tier"] = "Gold",
	},
	["Flash 2"] = {
		["description"] = "Replace a summoner spell with ''{{si|Flash}}''. Additionally, gain 70 summoner spell haste.",
		["tier"] = "Silver",
	},
	["Flashy"] = {
		["description"] = "Your {{si|Flash}} now has 3 charges with a {{tt|2-second cooldown|1.18 seconds after applying the 70 summoner spell haste from the global ARAM champion buff}} between casts (120 seconds recharge time for all 3 charges).<br><br>''If {{si|Flash}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Flash}}.''",
		["tier"] = "Gold",
	},
	["From Beginning to End"] = {
		["description"] = "Gain the {{ri|Dark Harvest}} and {{ri|First Strike}} keystone runes.",
		["tier"] = "Gold",
		["notes"] = [=[
		* {{ri|Dark Harvest}}
		** Base damage changed to {{pp|50 to 100}}.
		** Damage per soul changed to 20.
		** Bonus AD ratio changed to {{as|35% '''bonus''' AD}}.
		** AP ratio changed to {{as|25% AP}}.
		** Gain {{as|8 Souls}} if this is not your first augment.
		* {{ri|First Strike}}
		** Base gold increased to {{g|20}} from {{g|15}} (ARAM override value).
		** Bonus damage increased to 10% from 7%.
        ]=]
	},
	["Get Excited"] = {
		["description"] = "Scoring a champion {{tip|takedown}} grants you {{as|100% '''bonus''' movement speed}} and {{as|15% '''total''' attack speed}} for 4 seconds.",
		["tier"] = "Gold",
	},
	["Impassable"] = {
		["description"] = "Gain the {{ri|Aftershock}} and {{ri|Glacial Augment}} keystone runes.",
		["tier"] = "Gold",
		["notes"] = [=[
		* {{ri|Aftershock}}
		** Cooldown reduced to 15 seconds from 20.
		* {{ri|Glacial Augment}}
		** Cooldown reduced to 15 seconds from 25.
        ]=]	
	},
	["It's Critical"] = {
		["description"] = "Grants {{as|50% critical strike chance}}.",
		["tier"] = "Gold",
	},
	["It's Killing Time"] = {
		["description"] = "Upon casting your ultimate ability, you apply {{cai|Death Mark|Zed}} to all enemy champions (8 second cooldown). The mark stores 40% of all {{tt|post-mitigation|Damage calculated before modifiers}} damage you deal to the affected target, detonating after 5 seconds to deal {{as|true damage}} equal to the damage stored against them.",
		["tier"] = "Gold",
	},
	["Magic Missile"] = {
		["description"] = "Dealing damage to an enemy champion with an ability fires 3 missiles at them that each deal {{as|true damage}} equal to {{as|{{fd|0.3{{recurring|3}}}}% of the target's '''maximum''' health}}, increased to up to {{as|1%|health}} based on distance travelled (maximum damage reached at 1000 units). This effect can only trigger once every 6 seconds from the same cast.",
		["tier"] = "Gold",
	},
	["Marksmage"] = {
		["description"] = "Basic attacks deal {{as|'''bonus''' physical damage}} equal to {{as|75% AP}}.",
		["tier"] = "Gold",
	},
	["Minionmancer"] = {
		["description"] = "Your {{tip|pet|pets}} deal 40% increased damage as well as gain 40% {{as|'''bonus''' health}} and size.",
		["tier"] = "Gold",
	},
	["Nightstalking"] = {
		["description"] = "Scoring a {{tip|takedown}} against an enemy champion within 3 seconds of damaging them renders you {{tip|invisible}} for {{fd|1.5}} seconds, during which you also gain {{as|40% '''bonus''' movement speed}}. Attacking or casting abilites ends the stealth immediately.",
		["tier"] = "Gold",
	},
	["OK Boomerang"] = {
		["description"] = "{{as|Automatically}} cast an improved version of {{cai|Boomerang Blade|Sivir}} at the closest nearby enemy champion within 1250 units, dealing {{pp|40 to 200}} {{as|(+ 30% '''bonus''' AD)}} {{as|(+ 20% AP)}} {{tip|adaptive damage}} to enemies hit (10 second cooldown).",
		["tier"] = "Gold",
	},
	["Outlaw's Grit"] = {
		["description"] = "{{tip|Dash|Dashing}} or {{tip|blink|blinking}} grants 12 {{as|'''bonus''' armor}} and {{as|'''bonus''' magic resistance}} for 15 seconds, stacking up to 5 times for a total of 60 '''bonus''' resistances, and refreshing on subsequent triggers.",
		["tier"] = "Gold",
	},
	["Overflow"] = {
		["description"] = "Your abilities' {{as|mana}} costs are doubled, but you also gain 10% {{as|(+ {{fd|0.5}}% per 100 '''maximum''' mana)|mana}} increased damage as well as self and outgoing {{tip|heal|healing}} and {{tip|shield|shielding}}.",
		["tier"] = "Gold",
	},
	["Recursion"] = {
		["description"] = "Grants {{as|60 ability haste}}.",
		["tier"] = "Gold",
	},
	["Scopier Weapons"] = {
		["description"] = "Gain {{rd|200|100}} '''bonus''' attack range.",
		["tier"] = "Gold",
	},
	["Searing Dawn"] = {
		["description"] = "Gain {{cai|Sunlight|Leona}}.<br><br>{{sbc|Sunlight:}} Your damaging abilities mark enemies, causing them to take {{as|{{pp|40 to 200}}|magic damage}} {{as|'''bonus''' magic damage}} from your ally's next basic attack or ability hit against them ({{fd|0.75}}-second cooldown per target).",
		["tier"] = "Gold",
	},
	["Shrink Ray"] = {
		["description"] = "Basic attacks {{tip|on-hit}} reduce the target's damage dealt by 15% for 3 seconds, refreshing with each hit. Their size is also reduced significantly for the duration.",
		["tier"] = "Gold",
	},
	["Skilled Sniper"] = {
		["description"] = "Hitting an enemy champion with a basic ability while located at least {{tip|er|icononly=true}} 600 units away from them at the time of the hit reduces its '''current''' cooldown by 80% of its '''total''' cooldown, modified to 65% for [[damage over time]] abilities.",
		["tier"] = "Gold",
	},
	["Soul Siphon"] = {
		["description"] = "{{tip|Heal}} for 12% of the {{tt|post-mitigation damage|Damage calculated after modifiers}} dealt by your {{tip|critical strikes}}. Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Gold",
		["notes"] = [=[
        *  Any damage from {{tip|critical strike|Critical strikes}} will heal, including those from non-basic attack sources ({{cai|Noxian Diplomacy|Talon}}, {{cai|Volley|Ashe}}, etc<!--might heal from cosmetic crits?-->).
        ]=]	
	},
	["Tank Engine"] = {
		["description"] = "Scoring a champion {{tip|takedown}} generates a stack, stacking infinitely. For each stack, increase your {{as|'''maximum''' health}} and [[size]] by 5%. Lose 65% of stacks on death.",
		["tier"] = "Gold",
	},
	["Thread the Needle"] = {
		["description"] = "Grants 18% {{as|armor penetration}} and {{as|magic penetration|magic resistance}}.",
		["tier"] = "Gold",
	},
	["Transmute: Prismatic"] = {
		["description"] = "Gain one random Prismatic-tier augment.",
		["tier"] = "Gold",
	},
	["Upgrade Infinity Edge"] = {
		["description"] = "Upgrades {{ii|Infinity Edge}}, empowering it to gain {{iis|Sword of the Divine}} {{nie|Excoriate}}. Additionally, gain {{g|500}}.<br><br>{{sbc|Excoriate:}} Gain a random amount of {{as|'''bonus''' critical strike damage|critical damage}} that scales up to {{as|50% of your critical strike chance}}, with the value of this amount changing every {{fd|0.25}} seconds.",
		["tier"] = "Gold",
	},
	["Upgrade Sheen"] = {
		["description"] = "Upgrades all {{tip|Spellblade}} items, empowering the passive effect to deal additional {{as|'''bonus''' physical damage}} equal to {{as|4% of the target's '''maximum''' health}} and {{tip|heal}} you for {{as|{{fd|3.5}}% of the target's '''maximum''' health}}. Additionally, gain {{g|250}}.",
		["tier"] = "Gold",
	},
	["Vulnerability"] = {
		["description"] = "Damage dealt by items and damage over time effects can now {{tip|critical strike|critically strike}} for (145% + {{sti|{{as|'''bonus''' critical strike damage}}}}) damage (5 second cooldown per {{tip|cast instance}}). Additionally, gain {{as|25% critical strike chance}}.<br><br>If both [[File:Jeweled_Gauntlet_mayhem_augment.png|20px|link=|An icon for the ARAM: Mayhem augment Jeweled Gauntlet]] Jeweled Gauntlet and Vulnerability are equipped, only rolls the critical strike chance of the augment that has the higher critical damage (or either if equal).",
		["tier"] = "Gold",
		["notes"] = [=[
        * The interaction between ''Jeweled Gauntlet'' and ''Vulnerability'' may behave incorrectly with {{tip|persistent area damage}} effects.{{bug}}
        * ''Vulnerability'' has no effect if the source of the item damage or damage or time effect can already critically strike.
        ]=]
	},
	["With Haste"] = {
		["description"] = "Grants {{as|'''bonus''' movement speed}} equal to {{as|70% ability haste}}.",
		["tier"] = "Gold",
	},
	["Back to Basics"] = {
		["description"] = "Your [[champion ability|champion abilities]] deal 35% increased damage and you gain {{as|70 ability haste}} and 35% increased {{tip|heal|healing}} and {{tip|shield|shielding}} from all sources, but your ultimate ability is permanently {{tip|lockout|sealed}}.",
		["tier"] = "Prismatic",
	},
	["Biggest Snowball Ever"] = {
		["description"] = "Upgrades your {{si|Mark}} into a massive snowball, empowering it with an increased size radius and the ability to pass through non-champions. The snowball additionally explodes upon impact of the target hit to deal {{as|{{pp|200 to 350}}|magic damage}} {{as|(+ 100% '''bonus''' AD)}} {{as|(+ 60% AP)}} {{as|magic damage}} to all nearby enemies, {{tip|airborne|knock them up}} for {{fd|0.75}} seconds, and {{tip|slow}} them by 20% for 2 seconds. Additionally, your {{sis|Mark}} cooldown is reduced equivalent to 100 ability haste.<br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}. Non-champions hit by the snowball are {{tip|stun|stunned}} for {{fd|1.25}} seconds.''",
		["tier"] = "Prismatic",
	},
	["Blade Waltz"] = {
		["description"] = "Replace a summoner spell with [[File:Blade Waltz.png|20px|link=]] '''Blade Waltz'''.<br><br>{{sbc|Blade Waltz:}} {{tip|Blink}} to the target enemy champion. You then blink to the nearest other enemy champion every {{fd|0.25}} seconds over the next {{fd|1.75}} seconds, blinking up to 7 additional times. The last blink targets the primary target. Each time you blink to an enemy, deal {{as|{{pp|30 to 150}}|physical damage}} {{as|(+ 10% '''bonus''' AD)}} {{as|(+ 6% AP)}} {{as|physical damage}} to them and apply {{tip|on-hit}} effects at 50% effectiveness, up to a total of {{as|{{pp|30*6 to 150*6}}|physical damage}} {{as|(+ {{ap|10*6}}% '''bonus''' AD)}} {{as|(+ {{ap|6*6}}% AP)}} (45 second cooldown).<br><br>While '''Blade Waltz''' is active, you are {{tip|untargetable}} and {{tip|lockout|unable to act}}. This effect will end prematurely if there are no longer any nearby valid targets to blink to. An enemy can be blinked to more than once if there are no other valid targets in range.",
		["tier"] = "Prismatic",
	},
	["Can't Touch This"] = {
		["description"] = "Casting your ultimate grants you {{tip|invulnerability}} for 2 seconds (8 second cooldown).",
		["tier"] = "Prismatic",
	},
	["Circle of Death"] = {
		["description"] = "{{tip|Heal|Healing}} and {{stil|health regeneration}} you do causes you to deal 70% of that value in {{as|magic damage}} to the nearest enemy champion within 1000 units.",
		["tier"] = "Prismatic",
	},
	["Clown College"] = {
		["description"] = "Gain {{cis|Shaco}} {{ai|Backstab|Shaco}}, {{ai|Deceive|Shaco}} and {{ais|Hallucinate|Shaco}} explosion. Replace a summoner spell with ''{{ai|Deceive|Shaco}}''.<br><br>[[File:Backstab.png|20px|link=]] {{sbc|Passive - Backstab:}} Your basic attacks deal {{as|{{pp|20 to 35}}|physical damage}} {{as|(+ 50% '''bonus''' AD)}} {{as|(+ 35% AP)}} {{ccs|{{as|'''bonus''' physical damage}}|physical}} {{tip|on-hit}} when hitting an enemy from behind.<br><br>[[File:Deceive.png|20px|link=]] {{sbc|Active - Deceive:}} Become {{tip|invisible}} for up to 3 seconds and {{tip|blink}} to the target location within 400 units after a {{fd|0.125}}-second delay. Your next basic attack while in stealth deals {{as|100|physical damage}} {{as|(+ 150% '''bonus''' AD)}} {{as|(+ 55% AP)}} {{as|'''bonus''' physical damage}}, increased to{{ft|{{as|{{ap|100*1.55}}|physical damage}} {{as|(+ {{ap|150*1.55}}% '''bonus''' AD)}} {{as|(+ {{ap|55*1.55}}% AP)}} {{as|'''bonus''' physical damage}}|155% damage}}if [[File:Backstab.png|20px|link=]] ''Backstab'' was applied (45 second cooldown).<br><br>[[File:Hallucinate.png|20px|link=]] {{sbc|Passive - Hallucinate Death:}} Upon your death, release an explosion in a {{tip|cr|icononly=true}} 350 radius of your death location, dealing {{as|true damage}} equal to {{as|25% of target's '''maximum''' health}} to enemies within the area. Additionally, you deploy a {{ai|Jack in the Box|Shaco|box}} at the location of your death that instantly {{tip|fear|fears}} nearby enemies for 1 second. This box does not attack but lasts for 3 seconds.",
		["tier"] = "Prismatic",
	},
	["Courage of the Colossus"] = {
		["description"] = "{{tip|immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion grants a {{tip|shield}} for 3 seconds that absorbs {{pp|150 to 450}} {{as|(+ 4% '''maximum''' health)}} damage (5 second cooldown per {{tip|cast instance}}). Shields can stack between multiple triggers of this effect, though not refreshing the duration of previous shields.",
		["tier"] = "Prismatic",
	},
	["Cruelty"] = {
		["description"] = "{{tip|Immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion summons a comet above them that lands at their current location after 1 second, dealing {{as|{{pp|50 to 150}}|magic damage}} {{as|(+ 40% AP)}} {{as|(+ 4% of your '''maximum''' health)}} {{as|magic damage}} to enemies within a 300 radius (6 second cooldown per {{tip|cast instance}}).<br><br>For {{tip|airborne|displacement}} effects, the comet will be summoned at the displacement's end location.",
		["tier"] = "Prismatic",
	},
	["Dashing"] = {
		["description"] = "Abilities with {{tip|dash|dashes}} or {{tip|blink|blinks}} gain {{as|175 ability haste}}.",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * On {{ci|Kalista}}, this augment instead grants her {{as|125% '''bonus''' attack speed}}.[https://www.bilibili.com/video/BV1Tnm4B6E5a]
        ]=]		
	},
	["Draw Your Sword"] = {
		["description"] = "Become {{tip|melee}}, modifying your attack range to 200 (+ 100% '''bonus''' {{sti|attack range}} from augments) units. Additionally, gain {{as|24% '''bonus''' attack damage}}, {{as|20% '''bonus''' attack speed}}, {{as|24% '''bonus''' health}}, {{as|20% '''bonus''' movement speed}}, and 20% life steal. These bonuses are increased by {{pp|key=%|type=champion's default attack range|0 to 100 for 11|500 to 650|formula=10% for every 15 attack range starting from 500 attack range and with the maximum at 650 range}}.<br><br>''This augment is only available for {{tip|ranged}} champions.''",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * This augment is not offered if the champion has built {{ii|Runaan's Hurricane}}.
        ]=]	
        
	},
	["Dual Wield"] = {
		["description"] = "Your basic attacks launch a bolt at the target that fires after a {{tt|{{fd|0.225}}-second delay|Estimated}} {{tip|on-attack}}, deals 40% of the triggering attack's {{tt|pre-mitigation|Damage calculated before modifiers}} damage, and applies {{tip|on-hit}} effects at 40% effectiveness. Additionally, increase your {{as|'''total''' attack speed}} by {{as|10%|attack speed}}.",
		["tier"] = "Prismatic",
	},
	["Empyrean Promise"] = {
		["description"] = "Replace a summoner spell with ''{{iis|Empyrean Promise}}'' {{nie|Vigilance}} active. Additionally, gain {{as|15% heal and shield power}}.<br><br>{{sbc|Active - Vigilance:}} After a {{fd|0.25}}-second delay, {{tip|dash}} to the current location of the target allied champion and gain a {{pp|100 to 250}} {{as|(+ 100% AP)}} {{as|(+ 10% '''bonus''' health)}} {{tip|shield}} for 3 seconds. Upon arrival, grant the ally the same shield (20 second cooldown; 2000 range).",
		["tier"] = "Prismatic",
	},
	["Eureka"] = {
		["description"] = "Gain {{as|ability haste}} equal to {{as|30% AP}}.",
		["tier"] = "Prismatic",
	},
	["Fey Magic"] = {
		["description"] = "Damaging enemies with your ultimate ability {{tip|polymorph|polymorphs}} them into harmless critters for 2 seconds, during which their {{as|'''base''' movement speed}} is reduced by {{as|60|ms}}, and {{tip|disarm|disarms}} them for the same duration (15 second cooldown per target).",
		["tier"] = "Prismatic",
	},
	["Final Form"] = {
		["description"] = "Casting your ultimate ability empowers you for 10 seconds, causing you to gain a {{tip|shield}} for {{as|50% of your '''maximum''' health}}, {{as|20% omnivamp}}, and {{as|30% '''bonus''' movement speed}} for the duration (20 second cooldown).",
		["tier"] = "Prismatic",
	},
	["Giant Slayer"] = {
		["description"] = "Become tiny, reducing your size by 75% and granting you {{as|20% '''bonus''' movement speed}}. Additionally, deal {{pp|key=%|type=target's size|10;15;25;30|Small;Medium;Large;Extra Large}} '''bonus''' damage against enemy champions with greater size than you.",
		["tier"] = "Prismatic",
	},
	["Glass Cannon"] = {
		["description"] = "You gain a [[Health#Health_threshold|health threshold]] equal to {{sti|{{as|70% '''maximum''' health}}}} which cannot be {{tt|modified|By increases or decreases to maximum health}} nor {{tt|exceeded|By healing and health regeneration}} by any means. In return, you deal {{as|'''bonus''' true damage}} equal to {{rd|25%|15%}} of all of the damage you deal {{tt|pre-mitigation|Damage calculated before modifiers}}.",
		["tier"] = "Prismatic",
	},
	["Goldrend"] = {
		["description"] = "Damaging basic attacks or abilities against enemy champions deal {{as|{{pp|50 to 150}}|magic damage}} {{as|(+ 40% '''bonus''' AD)}} {{as|(+ 20% AP)}} {{as|'''bonus''' magic damage}}, and grant you {{g|30}} and {{as|25% '''bonus''' movement speed}} for {{fd|1.5}} seconds (30 second cooldown per champion).",
		["tier"] = "Prismatic",
	},
	["Goliath"] = {
		["description"] = "Grants {{as|35% '''bonus''' health}}, 15% {{tip|adaptive force}}, and 50% increased size.",
		["tier"] = "Prismatic",
	},
	["Infernal Conduit"] = {
		["description"] = "Your ability hits against champions apply a {{as|Burn}} for 3 seconds that deals{{ft|{{pp|6/3 to 60/3|color=magic damage}} {{as|(+ {{fd|4.{{recurring|6}}}}% '''bonus''' AD)}} {{as|(+ {{ap|6/3}}% AP)}} {{as|'''bonus''' magic damage}} per second|{{pp|6 to 60|color=magic damage}} {{as|(+ 14% '''bonus''' AD)}} {{as|(+ 6% AP)}} {{as|'''bonus''' magic damage}} over the duration}}(1 second cooldown per {{tip|cast instance}}). This {{as|Burn}} stacks infinitely and refreshes with each application.<br><br>Additionally, all of your {{as|Burn}} effects reduce the cooldowns of all your basic abilities by {{fd|0.08}} seconds for each tick of damage they deal to a target.",
		["tier"] = "Prismatic",
		["notes"] = [=[
		* {{tip|Persistent damage|Damage over time}} effects from all sources except items{{bug|2}} count as {{as|Burn}} sources for triggering the cooldown reduction.
        * {{sbc|Eligible Augments for {{as|Burn|buzzword3}}}}:  [[File:Firebrand_mayhem_augment.png|24px|link=]] Firebrand, [[File:Infernal_Conduit_mayhem_augment.png|24px|link=]] Infernal Conduit, [[File:Pressure_Cooker_mayhem_augment.png|24px|link=]] Pressure Cooker
        ]=]		
	},
	["Jeweled Gauntlet"] = {
		["description"] = "Your abilities can now {{tip|critical strike|critically strike}} for (145% + {{sti|{{as|'''bonus''' critical strike damage}}}}) damage. Additionally, gain {{as|25%|critical strike chance}} {{as|(+ {{fd|4.5}}% per 100 AP)}} {{as|critical strike chance}}.<br><br>If both Jeweled Gauntlet and [[File:Vulnerability mayhem augment.png|20px|link=|An icon for the ARAM: Mayhem augment Vulnerability]] Vulnerability are equipped, only rolls the critical strike chance of the augment that has the higher critical damage (or either if equal).",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * The interaction between ''Jeweled Gauntlet'' and ''Vulnerability'' may behave incorrectly with {{tip|persistent area damage}} effects.{{bug}}
        * ''Jeweled Gauntlet'' has no effect on abilities that can already critically strike.
        ]=]
	},
	["King Me"] = {
		["description"] = "Upon entering the enemy team's {{tip|warp gate|gate}} or [[Catapult]] for the first time, either of which are located near their [[spawn]], you become [[File:King Me buff.png|20px|link=]] {{as|Kinged|buzzword5}}, causing you to gain one random Prismatic-tier augment and the first eligible [[Legendary item]] in your inventory to be upgraded with improved stats. The [[Gold efficiency (League of Legends)|gold value]] of all {{tt|upgradeable stats|Includes AH, AP, AD, AS, AR, MR, and HP}} on the item is increased by exactly {{g|1000}}.<br><br>''King Me scans each item slot in the champion's inventory (from slots 1-6) for an eligible Legendary item, upgrading the first eligible item that is found.''",
		["tier"] = "Prismatic",
	},
	["Mad Scientist"] = {
		["description"] = "Upon acquiring this augment and each time you respawn, gain either 30% {{tip|adaptive force}}, {{as|20% '''bonus''' health}}, and 40% increased size or {{as|70 ability haste}}, {{as|40% '''bonus''' movement speed}}, and 40% reduced size.",
		["tier"] = "Prismatic",
	},
	["Master of Duality"] = {
		["description"] = "Basic attacks {{tip|on-hit}} grant {{as|{{pp|6 to 18}} ability power}} and damaging abilities once per {{tip|cast instance}} grant {{as|{{pp|3 to 9}} '''bonus''' attack damage}}, lasting for 5 seconds, with the duration of both refreshing on subsequent hits, and stacking infinitely.",
		["tier"] = "Prismatic",
	},
	["Mystic Punch"] = {
		["description"] = "Basic attacks {{tip|on-hit}} reduce the remaining cooldowns of your abilities by {{fd|1.25}} seconds.",
		["tier"] = "Prismatic",
	},
	["Ominous Pact"] = {
		["description"] = "Your abilities now have a {{tip|health resource|health cost}} of {{as|5% '''current''' health}} to cast them. In return, you gain {{as|ability power}} based on your {{as|'''missing''' health}}, up to {{as|{{pp|75 to 150}}|AP}} at {{as|70% '''missing''' health}}, {{pp|key=%|key1=%|type='''missing''' health|0 to 50 for 11|0 to 70|formula=0.714% per 1% '''missing''' health, capped at 70% '''missing''' health|showtype=false|color=movement speed}} {{as|(based on '''missing''' health)}} {{as|'''bonus''' movement speed}}, and {{pp|key=%|key1=%|type='''missing''' health|0 to 20 for 11|0 to 70|formula=0.286% per 1% '''missing''' health, capped at 70% '''missing''' health|showtype=false|color=omnivamp}} {{as|(based on '''missing''' health)}} {{as|omnivamp}}.",
		["tier"] = "Prismatic",
	},
	["Omni Soul"] = {
		["description"] = "Grants 3 random {{bi|Dragon Soul|Dragon Souls}}.",
		["tier"] = "Prismatic",
	},
	["Protein Shake"] = {
		["description"] = "Gain {{as|25%|heal and shield power}} {{as|(+ 35% per 100 '''bonus''' armor)}} {{as|(+ 35% per 100 '''bonus''' magic resistance)}} {{as|heal and shield power}}.",
		["tier"] = "Prismatic",
	},
	["Quest: Sneakerhead"] = {
		["description"] = "Assigns quests that require you to perform specific tasks while equipped with a particular [https://wiki.leagueoflegends.com/en-us/Category:Boots_items Boots item], which is granted to you for free during its respective quest. Finish the following quests, which are assigned to you in a random order:<br><ul><li>{{sbc|Quest - {{ii|Berserker's Greaves}}:}} Basic attack 25 times.</li><li>{{sbc|Quest - {{ii|Boots of Swiftness}}:}} Run 300 steps.<!--extremely vague, needs in-game testing--></li><li>{{sbc|Quest - {{ii|Ionian Boots of Lucidity}}:}} Cast 20 abilities.</li><li>{{sbc|Quest - {{ii|Mercury's Treads}}:}} Become afflicted by {{tip|crowd control}} 5 times.</li><li>{{sbc|Quest - {{ii|Plated Steelcaps}}:}} Reduce a total of 200 damage with {{nie|Plating}}.</li><li>{{sbc|Quest - {{ii|Sorcerer's Shoes}}:}} Deal a total of 1500 damage with abilities.</li></ul><br>{{sbc|Reward:}} Upon completing all of the above quests, you receive {{ii|Jarvan I's}}.<br><br>''You cannot purchase any Boots items while equipped with this augment. If you already have a Boots item, it is replaced by the Boots granted by this effect. Boots items gained from this effect cannot be sold.''<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Prismatic",
    },
	["Quest: Steel Your Heart"] = {
		["description"] = "{{sbc|Quest:}} Obtain {{ii|Heartsteel}} and accumulate over {{as|300 '''bonus''' health}} from ''Colossal Consumption''.<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, increase the {{as|'''bonus''' health}} gained from {{iis|Heartsteel}} ''Colossal Consumption'' by 200%.",
		["tier"] = "Gold",
	},
	["Quest: Urf's Champion"] = {
		["description"] = "{{sbc|Quest:}} Score 18 champion {{tip|takedown|takedowns}}.<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, you receive {{ii|The Golden Spatula}}.<br><br>''If your inventory is full at the time of quest completion, the item will be granted as soon as a slot in the inventory is available.''",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * {{ii|The Golden Spatula}}
        ** Attack damage changed to 90.
        ** Ability power changed to 110.
        ** Attack speed changed to 40%.
        ** Armor changed to 20.
        ** Magic resistance changed to 20.
        ** Movement speed changed to 10%.
        ** Critical strike chance changed to 15%.
        ** Health changed to 200.
        ** Base health regeneration changed to 50%.
        ** Mana changed to 200.
        ** Base mana regeneration changed to 100%.
        ** Life steal changed to 10%.
        ** {{sbc|Unique Passive - Doing Something:}}
        *** Burn radius changed to 400 units.
        *** Increased mana regeneration changed to 10%.
        *** Increased energy regeneration changed to 20%.
        *** {{sbc|Removed:}} No longer reduces the '''remaining''' cooldowns of your abilities by {{fd|0.2}} seconds every {{fd|0.25}} seconds.
        ]=]		
	},
	["Quest: Wooglet's Witchcap"] = {
		["description"] = "Gain a {{ii|Needlessly Large Rod}}.<br><br>{{sbc|Quest:}} Obtain {{ii|Rabadon's Deathcap}} and {{ii|Zhonya's Hourglass}}.<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, convert the items you obtained for the quest into {{ii|Wooglet's Witchcap}}.",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * {{ii|Wooglet's Witchcap}}
        ** Stasis cooldown changed to 60 seconds.
        ]=]		
	},
	["Scopiest Weapons"] = {
		["description"] = "Gain {{rd|250|150}} '''bonus''' attack range.",
		["tier"] = "Prismatic",
	},
	["Symphony of War"] = {
		["description"] = "Gain the {{ri|Conqueror}} and {{ri|Lethal Tempo}} keystone runes.",
		["tier"] = "Prismatic",
		["notes"] = [=[
		* {{ri|Conqueror}}
		** Adaptive force per stack changed to {{adaptive|3 to 5.5}}.
		** Healing changed to {{rd|10%|8%}} of damage dealt.
		* {{ri|Lethal Tempo}}
		** Bonus attack speed per stack changed to {{rd|13 to 18|8 to 12|pp=true|key=%}}.
		*** Maximum bonus attack speed changed to {{rd|13*6 to 18*6|8*6 to 12*6|pp=true|key=%}}.
		** {{sbc|Removed:}} No longer empowers basic attacks at maximum stacks to fire a bolt that deals '''bonus''' adaptive damage.
		** {{sbc|New Effect:}} At maximum stacks, gain {{sti|attack range|50 '''bonus''' attack range}} and increase the attack speed cap to 10.
        ]=]	
	},
	["Tap Dancer"] = {
		["description"] = "Basic attacks {{tip|on-hit}} against enemy champions and minions grant {{as|10 '''bonus''' movement speed}}, lasting for 5 seconds, refreshing on subsequent triggers, and stacking infinitely. Additionally, gain {{as|'''bonus''' attack speed}} equal to {{as|10% '''total''' movement speed}}.",
		["tier"] = "Prismatic",
	},
	["Transmute: Chaos"] = {
		["description"] = "Gain two completely random augments, excluding the other two offerings in your current assortment.",
		["tier"] = "Prismatic",
	},
	["Ultimate Awakening"] = {
		["description"] = "Casting your ultimate ability resets the {{sti|cooldowns}} of all your basic abilities and grants you 300 basic ability haste for 15 seconds (20 second cooldown). Additionally, gain 30 ultimate haste.",
		["tier"] = "Prismatic",
	},
	["Ultimate Revolution"] = {
		["description"] = "Casting your ultimate ability resets its {{sti|cooldown}} once its effect {{tt|starts|For instant-cast spells}} or has {{tt|elapsed|For duration-based spells}} (75 second cooldown, reset upon death).",
		["tier"] = "Prismatic",
	},
	["Windspeaker's Blessing"] = {
		["description"] = "Your {{tip|heal|heals}} and {{tip|shield|shields}} on yourself or allies grant the target {{pp|30 to 60}} {{as|'''bonus''' armor}} and {{as|'''bonus''' magic resistance}} for 3 seconds.",
		["tier"] = "Prismatic",
	},
	["Earthwake"] = {
		["description"] = "{{tip|Dash|Dashing}} or {{tip|blink|blinking}} causes you to leave behind a trail {{tip|cr|icononly=true}} from the location you moved to your destination that detonates after {{fd|0.75}} seconds in a 300 radius, dealing {{as|{{pp|90 to 250}}|physical damage}} {{as|(+ 125% '''bonus''' AD)}} {{as|(+ 60% AP)}} {{as|physical damage}} per explosion to enemies hit, reduced to 70% against {{tip|minions}}. Enemies can be affected only once every second from all {{tip|cast instance|cast instances}}, and the effect is not triggered if you move beyond 2000 units with the dash or blink.<br><br>This augment is only offered to up to 2 players on each team for a given game.",
		["tier"] = "Prismatic",
	},
	["Pandora's Box"] = {
		["description"] = "Gain one random Prismatic-tier augment. Additionally, your current augments transform into an equal number of completely random Prismatic-tier ones.",
		["tier"] = "Prismatic",
	},	
	["Slap Around"] = {
		["description"] = "{{tip|Immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion grants you {{adaptive|10}}, stacking infinitely (5 second cooldown per {{tip|cast instance}}). Lose 50% of stacks on death.",
		["tier"] = "Silver",
		["notes"] = [=[
		If the {{as|'''bonus''' attack damage}} and the {{as|ability power}} of the unit are '''equal''', the stat granted is always {{as|'''bonus''' AD}}.{{bug|2}}
		]=]	
	},
	["Hextech Soul"] = {
		["description"] = "Grants the {{bi|Hextech Dragon Soul}}, or a different {{bi|Dragon Soul}} if you aleady have it.",
		["tier"] = "Silver",
	},
	["Infinite Recursion"] = {
		["description"] = "Gain {{as|60 ability haste}}, increased by {{as|3|ability haste}} each time you score a champion {{tip|takedown}}.",
		["tier"] = "Prismatic",
	},
	["Donation"] = {
		["description"] = "Gain {{g|1750}} upon acquiring this augment.",
		["tier"] = "Gold",
	},
	["Double Tap"] = {
		["description"] = "Basic attacks that {{tip|critical strike|critically strike}} apply {{tip|on-hit}} effects an additional time. Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Prismatic",
	},
	["Empowered By The Faithful"] = {
		["description"] = "Granting a {{tip|heal}} or {{tip|shield}} to an allied champion blesses them for 8 seconds. Whenever a blessed ally damages an enemy champion, you generate a stack of ''Devotion'', stacking up to 50 times. Upon reaching maximum stacks, you unleash a shockwave that expands from your location in a massive radius and deals {{as|{{pp|50 to 300}}|magic damage}} {{as|(+ 750% heal and shield power)}} {{as|magic damage}} to enemies hit. Enemy champions damaged below a percentage of their {{as|'''maximum''' health}} equal to {{as|25% of your heal and shield power}} are {{tip|execute|executed}}.",
		["tier"] = "Prismatic",
	},
	["Firefox"] = {
		["description"] = "{{as|Automatically}} cast a modified version of {{cai|Fox-Fire|Ahri}}, gaining {{as|25% '''bonus''' movement speed}} that decays over 2 seconds and conjuring 3 flames that orbit you clockwise for up to {{fd|2.5}} seconds at a radius of {{tip|cr|icononly=true}} 150 units. The flames will {{tt|fly toward|On a 0.25-second delay after acquisition}} the nearest {{tip|sight|visible}} enemies within {{tip|cr|icononly=true}} 550 units, dealing {{pp|35 to 160}} {{as|(+ 25% '''bonus''' AD}} {{as|(+ 25% AP)}} {{tip|adaptive damage}}, reduced to{{ft|{{pp|35*0.3 to 160*0.3}} {{as|(+ {{ap|25*0.3}}% '''bonus''' AD}} {{as|(+ {{ap|25*0.3}}% AP)}}|30% of the original damage}}for enemies hit by subsequent flames from the same cast (7 second cooldown).",
		["tier"] = "Silver",
	},
	["Growth Spurt"] = {
		["description"] = "Replace a summoner spell with ''{{si|Growth Spurt}}''.<br><br>[[File:Growth Spurt.png|20px|link=]] {{sbc|Growth Spurt:}} {{#invoke:SpellData|geteffect|Growth Spurt}}",
		["tier"] = "Gold",
	},
	["Holy Snowball"] = {
		["description"] = "After using the {{si|Dash}} spell from {{si|Mark}}, you become {{tip|invulnerable}} for {{fd|1.5}} seconds upon arrival. Additionally, your {{sis|Mark}} cooldown is reduced equivalent to 100 ability haste.<br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}.''",
		["tier"] = "Prismatic",
	},
	["Triggered Inferno"] = {
		["description"] = "Your damaging basic attacks and abilities against at least one enemy {{tip|champion}} unique from the previous damaging hit made against champions generate a stack of ''Style'' for 6 seconds, refreshing on subsequent unique or non-unique hits and stacking up to 7 times. For each stack, gain {{as|{{pp|4.25 to 5 for 4|1 to 16|key=%}} '''bonus''' movement speed}}, up to a maximum of {{as|{{pp|4.25*7 to 5*7 for 4|1 to 16|key=%}}|ms}}.<br><br>Upon reaching maximum ''Style'' stacks, if an enemy champion is within range, you unleash a torrent of shots for {{rutngt|2.25}}. Over the first {{rutngt|2}}, you rapidly shoot at enemies within 600 units at sporadic times in {{tt|{{fd|0.2}}-second intervals|on average; total of 5 intervals of 0.231 and 5 of 0.198 seconds}} each (up to 10 times per enemy), dealing {{as|{{pp|20 to 40}}|physical damage}} {{as|(+ 40% AD)}} {{as|(+ 25% AP)}} {{as|physical damage}} with each shot, reduced by 75% against {{tip|minions}}. Enemies below {{as|30% of their '''maximum''' health}} are {{tip|critical strike|critically struck}} for{{ft|double damage|{{as|{{pp|20*2 to 40*2}}|physical damage}} {{as|(+ {{ap|40*2}}% AD)}} {{as|(+ {{ap|25*2}}% AP)}} {{as|physical damage}}}}(5 second cooldown). This effect ends prematurely if you become affected by {{tip|cast-inhibiting crowd control}}.<br><br>''Style stacks are represented by grades ([[File:Triggered Inferno Grade F.png|20px|link=]]→[[File:Triggered Inferno Grade E.png|20px|link=]]→[[File:Triggered Inferno Grade D.png|20px|link=]]→[[File:Triggered Inferno Grade C.png|20px|link=]]→[[File:Triggered Inferno Grade B.png|20px|link=]]→[[File:Triggered Inferno Grade A.png|20px|link=]]→[[File:Triggered Inferno Grade S.png|20px|link=]]). The stacks are consumed at the end of the shooting effect. Shot damage {{tip|applies lifesteal|applies}} {{sti|{{as|life steal}}}}.''",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * The ''Style'' stack count and corresponding symbol letter (see above) is indicated underneath your champion's model.
        * {{ci|Samira}} cannot use {{ai|Inferno Trigger|Samira}} during ''Triggered Inferno''.
        ]=]		
	},
	["Juiced"] = {
		["description"] = "Basic attacks against enemy champions deal {{as|'''bonus''' magic damage}} {{tip|on-hit}} equal to {{as|{{rd|7%|{{ap|7*0.8}}%}} of your '''maximum''' mana}}. This damage can {{tip|critically strike}} for {{critical damage|100}} '''bonus''' damage.",
		["tier"] = "Silver",
	},
	["Kill Secured"] = {
		["description"] = "Gain {{as|60% '''bonus''' movement speed}} towards enemy champions below {{as|40% of their '''maximum''' health}}.",
		["tier"] = "Silver",
	},
	["Phenomenal Evil"] = {
		["description"] = "Gain {{cai|Phenomenal Evil Power|Veigar}}.<br><br>{{sbc|Phenomenal Evil Power:}} Generate a permanent stack of ''Phenomenal Evil'' each time you damage an enemy champion with {{tip|ability damage}}. This effect cannot trigger more than once every second globally and once every 3 seconds from the same {{tip|cast instance}}. For each stack, gain {{as|1 ability power}}.<br><br>If this is not your first augment, start with 40 ''Phenomenal Evil'' stacks, granting you {{as|40 ability power}}.",
		["tier"] = "Gold",
		["notes"] = [=[
        * The 40 bonus stacks for selecting this augment as not your first augment are given once the first stack is earned.
        ]=]		
	},
	["Pinball"] = {
		["description"] = "Your {{si|Mark}} is empowered to instead throw a pinball, which deals {{as|{{pp|100 to 500}} '''bonus''' true damage}} and ricochets off of terrain that it collides with. Each time the pinball ricochets, its remaining travel distance is reset, it increases in radius by 25%, deals 20% increased damage, and reduces {{sis|Mark}} remaining cooldown by 30%. The pinball can ricochet up to 4 times, for a maximum radius increase of 100% and a damage increase of 80%. Additionally, your {{sis|Mark}} cooldown is reduced equivalent to 50 ability haste.<br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}.''",
		["tier"] = "Gold",
	},
	["Prom Queen"] = {
		["description"] = "{{as|Automatically}} cast a modified version of {{cai|The Quickness|Rakan}}, empowering you to break into a captivating sprint for 6 seconds. While empowered, you gain {{tip|ghosting}} and {{as|50% '''bonus''' movement speed}}, and enemies you {{tt|collide with|300 unit collision radius}} are {{tip|knockdown|knocked down}} and become {{tip|charm|charmed}} for {{fd|1.5}} seconds (35 second cooldown).<br><br>''A sparkly tiara will descend upon you {{fd|2.5}} seconds before the effect activates.''",
		["tier"] = "Prismatic",
	},
	["Purist - Caster"] = {
		["description"] = "Convert '''all''' of your {{as|'''bonus''' attack speed}} into {{as|ability haste}} at a rate of {{as|{{fd|0.65}} ability haste}} per {{as|1% '''bonus''' attack speed}}. Additionally, your abilities' '''total''' cooldowns are reduced by 10%.",
		["tier"] = "Silver",
	},
	["Quest: Icathia's Fall"] = {
		["description"] = "Gain {{ii|Bami's Cinder}}. You can now purchase {{ii|Hollow Radiance}} and {{ii|Sunfire Aegis}} in spite of the item limit imposed by {{nie|Immolate}}.<br><br>{{sbc|Quest:}} Obtain {{ii|Hollow Radiance}} and {{ii|Sunfire Aegis}}.<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, convert the items you obtained for the quest into {{ii|Void Immolation}}.",
		["tier"] = "Prismatic",
		["notes"] = [=[
		* While you have {{ii|Void Immolation}}, you will be imposed with {{nie|Immolate's}} item limit.
        * When gaining {{ii|Bami's Cinder}}, you will lose an {{ii|Ruby Crystal}} or a {{ii|Glowing Mote}} in your inventory as it will get upgraded with no gold returned back to you.{{bug}}
        ]=]
	},
	["Shrink Engine"] = {
		["description"] = "Scoring a champion {{tip|takedown}} generates a stack, stacking infinitely. For each stack, gain {{as|8 ability haste}} and {{as|1% '''bonus''' movement speed}}, and reduce your size by 4%. Lose 65% of stacks on death.<br><br>''Size reduction is capped at 80% (20 stacks).''",
		["tier"] = "Gold",
	},
	["Sonata"] = {
		["description"] = "Alternate between {{as|automatically}} casting a modified version of {{cai|Aria of Perseverance|Sona}} and modified {{ai|Song of Celerity|Sona}}, with the former being cast first (10 second cooldown).<br><br>{{sbc|Aria of Perseverance:}} {{tip|Heal}} yourself for 60 {{as|(+ 60% AP)}} and send out a tone to the {{tt|most wounded|Based on greatest % missing health}} allied champion within 1000 units that heals them for the same amount. Additionally, generate an {{tt|aura|400 unit radius, center-to-edge}} that grants you and tagged allied champions a 80 {{as|(+ 40% AP)}} {{tip|shield}} for {{fd|1.5}} seconds.<br><br>{{sbc|Song of Celerity:}} Gain {{as|30% '''bonus''' movement speed}} for 7 seconds. If you take damage during this time, the duration ends prematurely once or if 3 seconds have elapsed. Additionally, generate an {{tt|aura|400 unit radius, center-to-edge}} that grants tagged allied champions {{as|20% '''bonus''' movement speed}} for 3 seconds.",
		["tier"] = "Gold",
	},
	["Soul Eater"] = {
		["description"] = "{{tip|Immobilize|Immobilizing}} or {{tip|ground|grounding}} an enemy champion grants you {{as|30 '''bonus''' health}}, stacking infinitely (5 second cooldown per {{tip|cast instance}}).<br><br>If this is not your first augment, gain {{as|300 '''bonus''' health}}.",
		["tier"] = "Gold",
	},
	["Spin Me Right Round"] = {
		["description"] = "Replace a summoner spell with ''{{cai|Heroic Swing|Akshan}}'' ({{tt|10 second cooldown|5.88 seconds after applying the 70 summoner spell haste from the global ARAM champion buff}}, starts post-effect).<br><br>{{sbc|Heroic Swing - Active:}} You can activate ''Heroic Swing'' three times before the ability goes on cooldown, and you can use the third cast only after {{fd|0.5}} seconds of the second cast. An attack or movement command may be inputted to use the second and third casts.<br><br>[[File:Heroic Swing.png|20px|link=]] {{sbc|First Cast:}} Fire a hook in the target direction that embeds in the first [[terrain]] hit for 2 seconds. ''Heroic Swing's'' second cast can be used while the hook is attached. If the hook fails to attach or you become {{tip|immobilize|immobilized}}, {{tip|ground|grounded}}, or {{tip|polymorph|polymorphed}} within the duration, ''Heroic Swing'' is cancelled and placed on full cooldown.<br><br>[[File:Heroic Swing 2.png|20px|link=]] {{sbc|Second Cast:}} {{tip|dash|Swing}} around the terrain in either a clockwise or counterclockwise direction based on the position of the cursor {{tt|relative to your facing direction|Dash will move clockwise if the player's cursor is anywhere to the left of their champion from their facing direction (or perspective), and counterclockwise if the cursor is anywhere to their champion's right.}}, stopping upon colliding with an enemy champion or terrain. While swinging, fire at the nearest {{tip|sight|visible}} enemy within your {{sti|attack range}} (minimum 400 units) every {{rutngt|0.2}} to deal them {{as|{{pp|15 to 75}}|physical damage}} {{as|(+ 15% AD)}} {{times}} {{as|(1 + {{fd|0.3}} per 100% '''bonus''' attack speed)}} {{as|physical damage}} and apply {{tip|on-hit}} effects for each shot, with on-hit damage reduced to 25% effectiveness. The dash will be {{tip|knockdown|interrupted}} if you are affected by any {{tip|immobilize|immobilizing}} or {{tip|polymorph|polymorphing}} crowd control during the dash.<br><br>{{sbc|Third Cast:}} End the swing by {{tip|dash|jumping}} to the target location and fire one last shot at a nearby {{tip|sight|visible}} enemy.",
		["tier"] = "Silver",
	},
	["Stats!"] = {
		["description"] = "Gain 2 {{ii|Stat Bonus|Stat Anvils}}.",
		["tier"] = "Silver",
	},
	["Stats on Stats!"] = {
		["description"] = "Gain 3 {{ii|Stat Bonus|Stat Anvils}}, with a higher chance of obtaining Gold- and Prismatic-tier anvils.",
		["tier"] = "Gold",
	},
	["Stats on Stats on Stats!"] = {
		["description"] = "Gain 4 {{ii|Stat Bonus|Stat Anvils}}, with a higher chance of obtaining Gold- and Prismatic-tier anvils. Additionally, on the next round of augment selection, you gain an additional reroll per augment slot.",
		["tier"] = "Prismatic",
	},
	["Stuck in Here With Me"] = {
		["description"] = "Casting your ultimate ability grants you an aura for 2 seconds, growing in size over the duration to up to 500 units. After the duration, you {{tip|taunt}} all enemies within the aura for 2 seconds and gain 50% damage reduction for the same duration (30 second cooldown). Additionally, gain 30 ultimate haste.<br><br>''Aura is activated once the ultimate's effect {{tt|starts|For instant-cast spells}} or has {{tt|elapsed|For duration-based spells}}.''",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * On {{ci|Katarina}}, this augment will activate at the start of {{ais|R|Katarina}} channel.
        ]=]			
	},
	["Twin Fire"] = {
		["description"] = "Damaging abilities against enemy champions launch 1 {{as|(+ 1 per {{fd|33.33}}% critical strike chance)}} missiles at the target that each deal {{as|{{pp|10 to 30}}|magic damage}} {{as|(+ 7% '''bonus''' AD)}} {{as|(+ 7% AP)}} {{as|magic damage}} (5 second cooldown). Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Silver",
	},
	["Zealot"] = {
		["description"] = "Gain {{as|35%|as}} {{as|(+ 5% per 100 AP)}} {{as|'''bonus''' attack speed}} and {{as|25%|critical strike chance}} {{as|(+ 5% per 100 AP)}} {{as|critical strike chance}}.",
		["tier"] = "Silver",
	},
	["Hand of Baron"] = {
		["description"] = "Gain a modified {{bi|Hand of Baron}}, which only grants 25% increased {{tip|adaptive force}} and greatly empowers nearby allied {{tip|minions}}.",
		["tier"] = "Prismatic",
	},
	["Upgrade Sword of Blossoming Dawn"] = {
		["description"] = "Upgrades {{ii|Sword of Blossoming Dawn}}, empowering {{nie|Peppermint}} to have its healing increased by 250%. Additionally, you gain {{as|100% '''bonus''' attack speed}}.",
		["tier"] = "Prismatic",
	},
	["Adaptive Ward"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability to grant you {{pp|7 to 12}} {{as|'''bonus''' armor}} or {{as|'''bonus''' magic resistance}} for 6 seconds when it hits an enemy champion (4 second cooldown). This effect can stack up to a number of times.<br><br>The resistance type granted is based on the target's [[File:Rune_shard_Adaptive_Force.png|20px|link=]] [[adaptive force|adaptive type]]: {{as|'''bonus''' armor}} for {{as|physical|physical damage}} and {{as|'''bonus''' magic resistance}} for {{as|magic|magic damage}}.",
		["tier"] = "Silver",
	},
	["Don't Change the Channel"] = {
		["description"] = "For every second that you {{tip|channel}} an ability, you gain a {{pp|50 to 200}} {{as|(+ 50% AD)}} {{as|(+ 25% AP)}} {{as|(+ 10% '''bonus''' health)}} {{tip|shield}}. The shield quickly decays once you stop channeling.",
		["tier"] = "Silver",
	},
	["Bolstered"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a {{tip|shield}} effect, increasing the strength of the ability's shield by {{pp|key=%|key1=%|type=target's '''missing''' health|0 to 60 for 11|0 to 70|color=health}}.",
		["tier"] = "Silver",
	},
	["Forged By The Master"] = {
		["description"] = "Increases the damage dealt by your [[named item effect|item effects]] and augments by 45%.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Silver",
	},
	["It's Go Time"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a duration-based effect, empowering the ability to grant {{as|{{pp|25 to 45|key=%}} '''bonus''' movement speed}} for the effect's duration.",
		["tier"] = "Silver",		
	},
	["Pursuit of Power"] = {
		["description"] = "{{sbc|Quest:}} Hit an enemy champion with a specific {{tip|ability}} 10 times (counts up to 1 hit per champion per {{tip|cast instance}}).<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, increase the damage of the ability by 30%.",
		["tier"] = "Gold",
	},
	["Siphon"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability to {{tip|heal}} you for 30% of its {{tt|post-mitigation damage|Damage calculated after modifiers}} dealt to enemy champions.",
		["tier"] = "Silver",
	},
	["Snowday"] = {
		["description"] = "Your {{si|Mark}} deals 100% increased damage and has its cooldown reduced equivalent to 100 ability haste.<br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}.''",
		["tier"] = "Silver",
	},
	["Stackosaurus Rex"] = {
		["description"] = "Increase the number of permanent stacks you gain from abilities by 100%.",
		["tier"] = "Silver",
	},
	["Stay Resolute"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability to grant you {{pp|2;3|1;11}} {{as|'''bonus''' armor}} or {{as|'''bonus''' magic resistance}} permanently when it damages an enemy champion, stacking infinitely (5 second cooldown per target per {{tip|cast instance}}).<br><br>The resistance type granted is based on the target's [[File:Rune_shard_Adaptive_Force.png|20px|link=]] [[adaptive force|adaptive type]]: {{as|'''bonus''' armor}} for {{as|physical|physical damage}} and {{as|'''bonus''' magic resistance}} for {{as|magic|magic damage}}.<br><br>If this is not your first augment, gain 20 {{as|'''bonus''' armor}} and {{as|'''bonus''' magic resistance}}.",
		["tier"] = "Silver",
	},
	["Trusty Weapon"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability to generate a ''Friendship'' stack for 6 seconds when it hits an enemy champion, stacking infinitely. For each ''Friendship'' stack you have, the ability deals 5% increased damage.",
		["tier"] = "Silver",
	},
	["Archmage"] = {
		["description"] = "Whenever you cast an ability, refund the cooldown of another, randomly selected ability by 30% of the casted ability's cooldown.",
		["tier"] = "Prismatic",
	},
	["BONK!"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has an empowered basic attack effect, further enhancing the attack to deal 30% increased damage to the target and 30% of its damage to nearby enemies.",
		["tier"] = "Silver",
	},
	["Endless Decimation"] = {
		["description"] = "While in combat, {{as|automatically}} cast an improved version of {{cai|Q|Darius}}, winding up over {{fd|1.25}} seconds to slash in a {{tip|cr|icononly=true}} 460 radius around you. The slash deals {{as|{{pp|100 to 400}}|physical damage}} {{as|(+ 60% AD)}} {{as|(+ 40% AP)}} {{as|physical damage}} to enemies within the area (8 second cooldown). Enemies within the {{tip|cr|icononly=true}} 240 inner radius of the slash take{{ft|50% damage.|{{as|{{pp|100*0.5 to 400*0.5}}|physical damage}} {{as|(+ {{ap|60*0.5}}% AD)}} {{as|(+ {{ap|40*0.5}}% AP)}} {{as|physical damage}}.}}Additionally, for each enemy champion hit along the outer edge, you {{tip|heal}} for {{as|18% of your '''missing''' health}} and the cooldown of this effect is reduced by 10%, down to a minimum of 3 seconds.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["From Downtown"] = {
		["description"] = "{{sbc|Quest:}} Hit enemy champions with abilities while located at least {{tip|er|icononly=true}} 600 units away from them (at the time of the hit) 15 times (counts up to 1 hit per champion per {{tip|cast instance}}).<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, hitting enemy champions with abilities while located at least {{tip|er|icononly=true}} 600 units away from them at the time of the hit fires a meteor to their current location, which upon landing deals {{pp|75 to 200|color=magic damage}} {{as|(+ 50% '''bonus''' AD)}} {{as|(+ 20% AP)}} {{as|magic damage}} to enemies within the area (8 second cooldown per target per {{tip|cast instance}}). The meteor's damage and radius are increased based on your distance to the target at the time of the ability hit, increasing its damage by {{pp|0 to 230 for 11|600 to 3000|key=%|showtype=false|label1=distance to target}} and setting its radius to {{pp|150;225;337.5;506.3;759.4;1139.1;1708.6|600 to 3000|showtype=false|label1=distance to target}} units.<br><br>''Maximum meteor damage is {{pp|75*2.3 to 200*2.3|color=magic damage}} {{as|(+ {{ap|50*2.3}}% '''bonus''' AD)}} {{as|(+ {{ap|20*2.3}}% AP)}}.''",
		["tier"] = "Gold",
	},
	["Lil' Extra Help"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has an effect which empowers your basic attacks for a duration, further enhancing the attacks by granting you {{rd|150|100}} '''bonus''' attack range and {{as|{{rd|75%|40%}} '''bonus''' attack speed}} while the effect is active.",
		["tier"] = "Gold",
	},
	["Mercy's Strike"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability's cast to enhance your next basic attack. The enhanced attack has 300 '''bonus''' range, gains {{as|75% '''bonus''' attack speed}}, and deals {{as|'''bonus''' magic damage}} equal to {{as|3%|hp}} {{as|(+ 2% per 10% heal and shield power)}} {{as|of the target's '''maximum''' health}}. If the target is a {{tip|turret}}, the damage is modified to {{as|{{fd|2.5}}% of the target's '''maximum''' health}} {{as|'''bonus''' magic damage}}.",
		["tier"] = "Gold",
	},
	["Nature is Healing"] = {
		["description"] = "Upon entering a patch of {{tip|brush}}, you are {{tip|heal|healed}} for{{ft|{{pp|40 to 300}} {{as|(+ 15% of your '''missing''' health)}}|{{pp|40/6 to 300/6}} {{as|(+ {{ap|15/6}}% of your '''missing''' health)}} every {{fd|0.25}} seconds}}over {{fd|1.5}} seconds (20 second cooldown per brush patch).<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["Overextender"] = {
		["description"] = "Your launch with the ''Cannon Launcher'' is now empowered, increasing the launch range by 12,000 units and the impact damage by 50%, as well as the travel speed by a significant amount. Additionally, your {{si|Recall}} is now functional and is upgraded to {{si|Empowered Recall}}.<br><br>''This augment is only available on the [[File:Howling Abyss icon.png|20px|link=]] [[Butcher's Bridge]] map.''<br><br>''Total launch range is 18,500 units, reduced to 16,500 after your team's Outer turret is destroyed. Increased impact damage is {{as|{{pp|120*1.5 to 460*1.5}} magic damage}}.''",
		["tier"] = "Gold",
	},
	["Pat On The Back"] = {
		["description"] = "Whenever you are within 200 units of an allied champion, they pat you on the back, granting you a {{pp|50 to 150}} {{as|(+ 25% '''bonus''' movement speed)}} {{tip|shield}} and {{as|30% '''bonus''' movement speed}} for 3 seconds (9 second cooldown). Subsequent passes only refresh the duration of the effects.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["Porcupine"] = {
		["description"] = "You build up a burst of needles from within you when taking damage from enemy champions, storing up to {{pp|400 to 3900}} {{tt|pre-mitigation damage|Damage calculated before modifiers}} taken. After reaching the maximum damage stored, you consume the stored damage to burst the needles outward in a 400 radius, dealing {{pp|75 to 200|color=physical damage}} {{as|(+ 125% '''bonus''' armor)}} {{as|(+ 125% '''bonus''' magic resistance)}} {{as|physical damage}} to enemies hit and {{tip|slow|slowing}} them by 30% for 2 seconds.",
		["tier"] = "Gold",
	},
	["Pursuit of Haste"] = {
		["description"] = "Assigns quests that require you to hit enemy champions with a specific {{tip|ability}} a number of times (counts up to 1 hit per champion per {{tip|cast instance}}). There are two quest tiers, and each completed tier rewards you with {{as|ability haste}} on the ability.",
		["tier"] = "Gold",
		["questinfo"] = [=[
{| class="article-table"
!Tier
! style="width: 250px;" | <center>Quest</center>
! style="width: 300px;" | Reward
|-
| <center>1</center>
|Hit an enemy champion with the ability 10 times.
|Reduce the cooldown of the ability equivalent to 80 ability haste.
|-
| <center>2</center>
|Hit an enemy champion with the ability 20 additional times (30 hits total).
|Reduce the cooldown of the ability equivalent to an additional 80 ability haste (160 ability haste total).
|}
        ]=]
	},
	["Ravenous Bind"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a {{tip|immobilize|immobilizing}} or {{tip|ground|grounding}} effect, empowering the ability to deal {{pp|15 to 90|color=magic damage}} {{as|(+ 10% AP)}} {{as|(+ {{fd|0.5}}% of your '''maximum''' health)}} {{as|magic damage}} to affected targets and {{tip|heal}} you for {{pp|75 to 300}} {{as|(+ 5% AP)}} {{as|(+ 12% '''bonus''' health)}}. The heal is increased by up to 50% based on how long the ability's cooldown is.",
		["tier"] = "Gold",
	},
	["Rejuvenation"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability's cast to {{tip|heal}} you for {{pp|30 to 100}} {{as|(+ 25% '''bonus''' AD)}} {{as|(+ 15% AP)}} {{as|(+ 5% '''bonus''' health)}}. This is increased by up to 50% based on how long the ability's cooldown is, for a maximum heal of {{pp|30*1.5 to 100*1.5}} {{as|(+ {{ap|25*1.5}}% '''bonus''' AD)}} {{as|(+ {{ap|15*1.5}}% AP)}} {{as|(+ {{ap|5*1.5}}% '''bonus''' health)}}.",
		["tier"] = "Gold",
	},
	["Shark Bait"] = {
		["description"] = "Upon taking {{tip|death|fatal damage}}, you become a ''Shark Bait'', causing you to enter a {{tip|zombie state}} for {{fd|3.5}} seconds, during which your {{as|movement speed}} is set to a {{as|static 400|ms}}, you gain {{tip|ghosting}}, and enemies within 400 units of you are {{tip|slow|slowed}} by 40%. At the end of the duration, a massive shark emerges from beneath you that lets out a powerful chomp (400 radius), dealing {{pp|120 to 350|color=magic damage}} {{as|(+ 30% of target's '''missing''' health)}} {{as|magic damage}} to all enemies within the area and {{tip|airborne|knocking them up}} for 1 second.<br><br>''While under the zombie state, you are able to move and become {{tip|invulnerability|invulnerable}}, {{tip|untargetable}}, and {{tip|cc-immune|immune to crowd control}}, but you are also rendered unable to declare {{tip|basic attacks}}, cast {{tip|abilities}}, use [[summoner spell]]s, and [[active ability items|activate items]].''<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["Shark Tempest"] = {
		["description"] = "Your {{si|Mark}} is empowered to circle sharks around it in a 300 radius, dealing {{as|{{pp|100 to 200}} magic damage}} to enemies it passes through as it travels and {{tip|slow|slowing}} targets hit by 40% for 1 second. If the missile hits an enemy champion, the sharks circle around their location in a 425 radius instead for 3 seconds, dealing{{ft|{{pp|30 to 90|color=magic damage}} {{as|(+ 25% '''bonus''' AD)}} {{as|(+ 15% AP)}} {{as|magic damage}} every second|{{pp|30*3 to 90*3|color=magic damage}} {{as|(+ {{ap|25*3}}% '''bonus''' AD)}} {{as|(+ {{ap|15*3}}% AP)}} {{as|'''total''' magic damage}} over the duration}}to enemies within the area and {{tip|slow|slowing}} them by 40% for 3 seconds.<br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}.''<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
		["notes"] = [=[
        * The damage dealt by this augment counts as {{tip|area damage}}, thus it is able to trigger {{tip|spell effects}}.
        ]=]			
	},
	["Snowblast"] = {
		["description"] = "Empowers the {{si|Dash}} spell from {{si|Mark}} to deal 100% increased damage and upon arrival cause you to {{tip|airborne|knock up}} the target for {{fd|0.5}} seconds and {{tip|airborne|knock back}} nearby enemies. Additionally, your {{sis|Mark}} cooldown is reduced equivalent to 100 ability haste. <br><br>''If {{si|Mark}} is not equipped, you will be prompted to replace one of your summoner spells with {{si|Mark}}.''<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["Terrain'd"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that spawns [[terrain]], empowering the ability to deal {{pp|20 to 180|color=magic damage}} {{as|(+ 20% AP)}} {{as|magic damage}} to enemies near the terrain. This damage is increased{{ft|by 200%|to {{pp|20*3 to 180*3|color=magic damage}} {{as|(+ {{ap|20*3}}% AP)}}}}if the ability is an ultimate.",
		["tier"] = "Gold",
		["notes"] = [=[
        * The damage dealt by this augment counts as {{tip|area damage}}, thus it is able to trigger {{tip|spell effects}}.
        ]=]		
	},
	["Tooth Fairy"] = {
		["description"] = "When you deal {{tt|post-mitigation damage|Damage calculated after modifiers}} to an enemy champion equal to or more than {{as|25% of their '''maximum''' health}} within {{fd|2.5}} seconds, they drop a ''Tooth'' on the ground (4 second cooldown per target). You can pick up this ''Tooth'' by moving over it, granting you a ''Dental Records'' stack. For each stack, you gain 3 {{as|lethality}} and {{as|flat magic penetration}}.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Gold",
	},
	["Warlock Juicebox"] = {
		["description"] = "Gain {{as|10%|omnivamp}} {{as|(+ 3% per 100 AP)}} {{as|omnivamp}}.",
		["tier"] = "Gold",
	},
	["Wee Woo Wee Woo"] = {
		["description"] = "Gain {{pp|key=%|key1=%|type=target's '''missing''' health|0 to 50 for 11|0 to 75|showtype=false|color=ms}} {{as|(based on target ally's '''missing''' health)|hp}} {{as|'''bonus''' movement speed}} while facing toward nearby allied champions, lingering for 2 seconds after no longer facing them. Your {{tip|heals}} and {{tip|shields}} are also increased by {{pp|key=%|key1=%|type=target's '''missing''' health|0 to 50 for 11|0 to 75|color=health}}.",
		["tier"] = "Gold",
	},
	["Yowch, My Coins!"] = {
		["description"] = "Enemy champions that you score a {{tip|takedown}} against drop {{pp|6 to 10}} coins, with each coin landing 500 units away from the location of their death and lasting 10 seconds. You or allied champions can collect the coins by moving over them, granting {{g|15}} for each coin collected.",
		["tier"] = "Gold",
	},
	["Chain Reaction"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a {{tip|airborne|knock back}} effect, empowering the ability to trigger a chain reaction effect when displaced champions hit other champions or terrain within 200 units. If a knocked back champion collides with another enemy champion during their displacement, the champions they collided with are dealt {{as|{{pp|100 to 400}} magic damage}} and {{tip|airborne|knocked up}} for {{fd|0.5}} seconds. If they collide with terrain during their displacement, they will rebound to take {{as|{{pp|150 to 800}} magic damage}} and become {{tip|airborne|knocked up}} for {{fd|0.75}} seconds and {{tip|stun|stunned}} for {{fd|0.5}} seconds. The knock up duration is increased to up to {{fd|1.1}} seconds based on how long the ability's cooldown is.<br><br>If the upgraded ability is an ultimate, this effect deals 250% damage, increasing the champion collision damage to {{pp|100*2.5 to 400*2.5|color=magic damage}} and the terrain collision damage to {{pp|150*2.5 to 800*2.5|color=magic damage}}.",
		["tier"] = "Gold",
	},
	["Echo Cast"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability's cast to summon a {{tip|clone}} of your champion that is {{tip|untargetable}} and moves up to 500 units towards your cursor. The clone then casts the ability it was summoned from after a {{fd|0.25}}-second delay, mimicking the active effects of the casted spell and disappearing after it finishes casting.",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * Clone movement speed is 1000.
        * Clone has a maximum lifetime of 7 seconds.
        ]=]
	},
	["En Passant"] = {
		["description"] = "You can now identify the {{as|Vitals|buzzword}} of enemy champions within {{tt|2000 units|Estimated}}, marked as an arc around them and pointing towards a specific direction. Dealing damage to a target with a basic attack or ability while you are facing in the direction of their exposed {{as|Vital|buzzword}} will consume it, dealing {{as|'''bonus''' true damage}} equal to {{as|6%|hp}} {{as|(+ {{fd|1.5}}% per En Passant stack)|buzzword7}} {{as|of the target's '''maximum''' health}}, {{tip|heal|healing}} you for {{pp|50 to 200}} {{as|(+ 5% '''missing''' health)}}, and granting you {{as|50%|ms}} {{as|(+ 5% per En Passant stack)|buzzword7}} {{as|'''bonus''' movement speed}} that decays over 2 seconds. Consuming a target's {{as|Vital|buzzword}} also grants you an {{as|En Passant|buzzword7}} stack for 8 seconds, refreshing on subsequent {{as|Vital|buzzword}} triggers and stacking up a number of times. Each {{as|En Passant|buzzword7}} stack increases the consumed {{as|Vital|buzzword}} damage and {{as|'''bonus''' movement speed}}.<br><br>{{as|Vitals|buzzword}} on targets become exposed instantly once you are within range and remain exposed until you die. Once a target's {{as|Vital|buzzword}} is consumed, you identify a new {{as|Vital|buzzword}} on them pointing in a different direction from the previous after 4 seconds.",
		["tier"] = "Prismatic",
	},
	["Hellbent"] = {
		["description"] = "Generate a stack of ''Revivemaxxing'' for each enemy champion you hit with basic attacks {{tip|on-hit}} or abilities, lasting for 6 seconds, refreshing on subsequent hits, and stacking up to 10 times. At maximum stacks, you become {{as|Hellbent}}.<br><br>{{as|{{sbc|Hellbent:}}}} Upon taking {{tip|death|lethal damage}}, you enter {{tip|resurrection}} for 4 seconds, during which you are {{tip|invulnerable}}, {{tip|untargetable}}, and {{tip|lockout|unable to act}}. Afterwards, you revive with {{as|{{pp|35 to 75|key=%}} of your '''maximum''' health}} (90 second cooldown). Additionally, you become empowered for the next 15 seconds, granting you {{as|{{pp|25*0.6 to 200*0.6}} '''bonus''' Attack Damage}} or {{as|{{pp|25 to 200}} Ability Power}} ([[Adaptive force|Adaptive]]), {{as|{{pp|20 to 40|key=%}} '''bonus''' movement speed}} while facing toward nearby enemy champions, and {{as|{{pp|15 to 30|key=%}} omnivamp}} for the duration.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Prismatic",
	},
	["Multishot"] = {
		["description"] = "Assigns quests that require you to hit enemy champions with a specific {{tip|ability|ability's}} missile a number of times (counts up to 1 hit per champion per {{tip|cast instance}}). There are six quest tiers, and each completed tier rewards you with an additional missile fired on the ability's cast. The reward effect also modifies the ability to fire all of its missiles in a cone. Subsequent missile hits from the same cast against the same enemy deal 30% damage.<br><br>''Hit requirements as denoted below are rounded down to whole numbers, with a minimum value of 1.''",
		["tier"] = "Prismatic",
		["questinfo"] = [=[
{| class="article-table"
!Tier
! style="width: 300px;" | <center>Quest</center>
! style="width: 250px;" | Reward
|-
| <center>1</center>
|Hit an enemy champion with the ability's missile '''(50{{divided by}}Ability's Base CD)''' times.
|<center>Ability fires an additional missile.<br>(2 missiles total)</center>
|-
| <center>2</center>
|Hit an enemy champion with the ability's missile '''(250{{divided by}}Ability's Base CD)''' more times.
|<center>Ability fires an additional missile.<br>(3 missiles total)</center>
|-
| <center>3</center>
|Hit an enemy champion with the ability's missile '''(700{{divided by}}Ability's Base CD)''' more times.
|<center>Ability fires an additional missile.<br>(4 missiles total)</center>
|-
| <center>4</center>
|Hit an enemy champion with the ability's missile '''(2000{{divided by}}Ability's Base CD)''' more times.
|<center>Ability fires an additional missile.<br>(5 missiles total)</center>
|-
| <center>5</center>
|Hit an enemy champion with the ability's missile '''(4000{{divided by}}Ability's Base CD)''' more times.
|<center>Ability fires an additional missile.<br>(6 missiles total)</center>
|-
| <center>6</center>
|Hit an enemy champion with the ability's missile '''(8000{{divided by}}Ability's Base CD)''' more times.
|<center>Ability fires an additional missile.<br>(7 missiles total)</center>
|}
        ]=]		
	},
	["Overloaded"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability to have its cooldown reset whenever you cast a different ability.",
		["tier"] = "Prismatic",
	},
	["Pin Cushion"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a duration-based effect, empowering it to cause basic attacks during the ability's effect to apply ''Nail'' stacks against enemy champions. At the end of the ability's duration, or if you die, the stacks on all targets are consumed, dealing {{pp|20 to 60|color=physical damage}} {{as|physical damage}} per ''Nail'' stack on the target. If this effect would deal lethal damage to the target, the stacks are consumed immediately. Additionally, once a target's stacks are consumed, you gain {{as|10 '''bonus''' movement speed}} per consumed stack for 3 seconds.",
		["tier"] = "Prismatic",
	},
	["Quickstep"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability's cast to cause you to {{tip|dash}} up to 350 units towards your cursor.",
		["tier"] = "Gold",
	},
	["Rite of Ascension"] = {
		["description"] = "Scoring a {{tip|takedown}} against an enemy champion within 3 seconds of damaging them causes them to leave behind their ''Essence'' for 8 seconds. You can basic attack the ''Essence'' within 400 units to consume it: causing you to {{tip|blink}} to its location after winding up for {{fd|1.25}} seconds, during which you are {{tip|untargetable}} (except to {{tip|turrets}}), {{tip|displacement immune}}, and {{tip|lockout|unable to act}}. Upon consumption of the ''Essence'', you gain {{as|100% '''bonus''' movement speed}} decaying over 2 seconds, {{tip|heal}} yourself for {{pp|75 to 300}} {{as|(+ 50% '''bonus''' AD)}} {{as|(+ 25% AP)}}, and reset the cooldowns of your basic abilities. The heal is increased by {{pp|key=%|key1=%|type=your '''missing''' health|0 to 100 for 11|0 to 100|color=health}}, for a maximum heal of {{pp|75*2 to 300*2}} {{as|(+ {{ap|50*2}}% '''bonus''' AD)}} {{as|(+ {{ap|25*2}}% AP)}}.",
		["tier"] = "Prismatic",
	},
	["Spell Split"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a missile, empowering the ability's missile to split in two over {{fd|0.25}} seconds upon reaching maximum range, or when recast. Each of the split missiles fire perpendicularly in opposite directions and apply the same effects to enemies they hit. Subsequent missile hits from the same cast against the same enemy deal 30% damage.<br><br>''Recast can be used after {{fd|0.15}} seconds of the initial cast.''",
		["tier"] = "Prismatic",
	},
	["Spirit Bomb"] = {
		["description"] = "Your {{tip|heal|healing}} and {{tip|shield|shielding}} on yourself or allies builds up a ''Spirit Bomb'' on top of you. Once you have healed and shielded a combined total of {{pp|200 to 2000}}, you toss the ''Spirit Bomb'' onto the {{tt|most wounded|Lowest health percent}} allied champion over {{fd|1.1}} seconds. Upon impact, the ''Spirit Bomb'' explodes in a 475 radius to {{tip|heal}} allied champions within the area for {{pp|5 to 15|key=%|color=health}} {{as|(+ 3% per 100 AP)}} {{as|of their '''missing''' health}} and grants them a {{tip|shield}} for 2 seconds that absorbs damage equal to {{pp|10 to 25|key=%|color=health}} {{as|(+ 2% per 100 AP)}} {{as|of their '''current''' health}}.<br><br>''Healing and shielding from this effect do not count toward the Spirit Bomb's trigger condition.''<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Prismatic",
		["notes"] = [=[
        * The toss range for the ''Spirit Bomb'' is global; it will target the lowest-health ally on the map.
        ]=]	
	},
	["Squishy Slappy Grab"] = {
		["description"] = "When an enemy champion is within 450 units of you, after a {{fd|1.5}}-second delay, you send out ''Squishy Slappy Hands'' that latch onto all nearby enemy champions within 800 units, forming a {{tip|tether}} between yourself and each target for 4 seconds (30 second cooldown). While the tethers persist (950 tether radius), your next basic attack is empowered to {{tip|airborne|pull}} all tethered enemies toward you, dealing {{pp|50 to 150|color=magic damage}} {{as|(+ 15% '''bonus''' health)}} {{as|magic damage}} to affected targets and {{tip|stun|stunning}} them for {{fd|0.25}} seconds after the pull ends. Targets are pulled over 450 units, reduced to 350 for those farther away from you. Additionally, you gain a {{pp|100 to 300}} {{as|(+ 70% '''bonus''' armor)}} {{as|(+ 70% '''bonus''' magic resistance)}} {{tip|shield}} for each pulled enemy, lasting for {{fd|2.5}} seconds.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Prismatic",
	},
	["Surge Field"] = {
		["description"] = "Upon casting your ultimate ability, you spawn a surge zone beneath you that has a 300 radius. While you are within the zone, you gain {{as|50 ability haste}} and {{as|40% '''bonus''' movement speed}}, and your damage dealt to enemy champions fires missiles at them that deal 20% of the triggering damage instance {{tt|pre-mitigation|Damage calculated before modifiers}} as {{as|'''bonus''' magic damage}}. The missile effect cannot trigger from itself.<br><br>The zone lasts indefinitely as long as you stay within its radius. If you leave the zone's radius for the first time, it moves to your current location. Exiting the zone a second time causes it to disappear if you do not re-enter the area within {{fd|1.25}} seconds.<br><br>{{as|'''This augment is currently disabled.'''|buzzword3}}",
		["tier"] = "Prismatic",
	},
	["Terror"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability's cast to {{tip|fear}} all enemies within 450 units of you for {{fd|1.75}} seconds (30 second cooldown).",
		["tier"] = "Silver",
	},
	["Titan's Resolve"] = {
		["description"] = "You generate a stack of ''Juggernauting'' for each instance of damage you deal or take (excluding [[damage over time]]), lasting for 6 seconds and refreshing on subsequent damage dealt or taken. For every 7 stacks of ''Juggernauting'', you gain {{as|{{pp|25*0.6 to 75*0.6}} '''bonus''' Attack Damage}} or {{as|{{pp|25 to 75}} Ability Power}} ([[Adaptive force|Adaptive]]), {{pp|5 to 10}} {{as|'''bonus''' armor}} and {{as|'''bonus''' magic resistance}}, 10% increased size, and 8% {{tip|tenacity}}.<br><br>''Stacks expire one by one when the duration ends, with the decay rate being faster the more stacks you have.''",
		["tier"] = "Prismatic",
	},
	["Tripleshot"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that is [[unit-targeted]] and fires a missile, empowering the ability to fire its missiles at two additional enemies near the primary target. Subsequent hits from the same cast against the same enemy deal 30% damage.",
		["tier"] = "Prismatic",
	},
	["Snap Back"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering the ability with a recast. Using the recast causes you to {{tip|blink}} back to your original casting position of the ability and explode to deal {{pp|100 to 300|color=magic damage}} {{as|(+ 20% AD)}} {{as|(+ 20% AP)}} {{as|magic damage}} to nearby enemies.<br><br>{{as|'''This augment exists in the internal augment data but appears to be disabled.'''|gold}}",
		["tier"] = "Gold",
	},
	["Reload"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that has a duration-based effect, causing basic attacks {{tip|on-hit}} during the ability to reduce its '''remaining''' cooldown by {{pp|0.15 to 0.35}} seconds.<br><br>{{as|'''This augment exists in the internal augment data but appears to be disabled.'''|gold}}",
		["tier"] = "Gold",
	},
	["Upgrade Ravenous Hydra"] = {
		["description"] = "Upgrades {{ii|Ravenous Hydra}}, increasing its life steal stat to {{as|20%|omnivamp}} and empowering {{nie|Cleave}} to trigger its effect on {{tip|ability}} hits against enemies (1 second cooldown per ability). Additionally, gain {{g|500}}.",
		["tier"] = "Gold",
	},
	["Upgrade Sundered Sky"] = {
		["description"] = "Upgrades {{ii|Sundered Sky}}, empowering {{nie|Lightshield Strike}} with an increased heal health ratio of {{as|9% of your '''missing''' health}} and a reduced cooldown of 5 seconds. Additionally, gain {{g|500}}.",
		["tier"] = "Gold",		
	},
	["Ultra Hydra"] = {
		["description"] = "You can now purchase {{ii|Tiamat}}, {{ii|Profane Hydra}}, {{ii|Ravenous Hydra}}, and {{ii|Titanic Hydra}} in spite of the item limit imposed by {{nie|Hydra}}. Purchasing a Legendary-tier {{nie|Hydra}} item (excluding {{ii|Stridebreaker}}) grants you a {{ii|Tiamat}} for free.<br><br>{{sbc|Quest:}} Obtain {{ii|Profane Hydra}}, {{ii|Ravenous Hydra}}, and {{ii|Titanic Hydra}}.<br><br>{{sbc|Reward:}} Upon completing your {{sbc|Quest}}, convert the items you obtained for the quest into {{ii|Ultra Hydra}}.",
		["tier"] = "Prismatic",
		["notes"] = [=[
		* While you have {{ii|Ultra Hydra}}, you will be imposed with {{nie|Hydra's}} item limit.
		* {{nie|Hydra}} items cannot be sold while equipped with this augment.
		* While equipped with this augment, the passive and active effects of all {{nie|Hydra}} items are no longer considered unique.
		** The {{nie|Cleave}} passive effects of {{ii|Tiamat}}, {{ii|Profane Hydra}}, {{ii|Ravenous Hydra}}, and {{ii|Titanic Hydra}} will all trigger at the same time, creating multiple damaging area of effects with each attack if multiple ''Hydra'' items are in the inventory.
		** The cooldowns of the active effects are not shared; activating the active effect of one ''Hydra'' item does not place the others on cooldown.
        ]=]		
	},
	["Upgrade Death's Dance"] = {
		["description"] = "Upgrades {{ii|Death's Dance}}, empowering {{nie|Ignore Pain}} with an increased damage reduction of {{rd|40%|15%}} and {{nie|Defy}} with an increased heal AD ratio of {{as|125% '''bonus''' AD}}. {{nie|Defy's}} healing is also granted instantly upon the passive effect being triggered rather than over 2 seconds. Additionally, gain {{g|250}}.",
		["tier"] = "Silver",
	},
	["Get Jinxed"] = {
		["description"] = "Replace a summoner spell with ''{{si|Get Jinxed!}}''.<br><br>[[File:Get Jinxed!.png|20px|link=]] {{sbc|Get Jinxed!:}} {{#invoke:SpellData|geteffect|Get Jinxed!}}",
		["tier"] = "Gold",
		["notes"] = [=[
		* The rocket has a collision radius of 50 units on terrain and 150 units against champions.
		* Once propelled, the rocket travels at an initial speed of 250 for the first {{fd|0.5}} seconds, before accelerating to 750. After another {{fd|1.5}} seconds, it decelerates to a near halt at a speed of 50 for {{fd|0.6}} seconds, then instantly accelerates to 1400 for the remainder of its flight.
        ]=]		
	},
	["Third Times the Harm"] = {
		["description"] = "Your basic attacks {{tip|on-hit}} against enemy champions apply a mark to the target for 4 seconds, refreshing on subsequent hits. Every third attack {{tip|on-hit}} against the marked target grants you a stack and deals {{as|'''bonus''' true damage}} equal to {{as|{{rd|6%|3%}} of the target's '''maximum''' health}} {{as|(+ {{rd|10|5}} per stack you have)|true damage}}.<!--Are the stacks you generate unique to the target?-->",
		["tier"] = "Prismatic",
	},
	["Big Shot"] = {
		["description"] = "Convert 75% of your {{as|'''total''' attack speed}} into {{as|critical strike damage}}, at a rate of {{as|{{fd|0.67}}% critical strike damage}} per {{as|1% attack speed}}. Additionally, you gain {{as|25% '''bonus''' attack damage}} and {{as|35% critical strike damage}}.",
		["tier"] = "Prismatic",
	},
	["Sound Barrier"] = {
		["description"] = "Your {{tip|shield|shields}} on yourself or allies grant {{tip|ghosting}} and {{as|{{pp|20 to 40|key=%}}|ms}} {{as|(+ {{fd|0.5}}% per 1% heal and shield power)}} {{as|'''bonus''' movement speed}} that decays over {{fd|1.5}} seconds ({{fd|1.5}}-second cooldown per target).",
		["tier"] = "Silver",
	},
	["Double Time"] = {
		["description"] = "Dealing damage to an enemy champion with two separate abilities within 4 seconds causes the second ability to deal {{as|'''bonus''' magic damage}} equal to {{as|10% '''maximum''' mana}} and permanently increase your {{as|'''maximum''' mana by 25}} (4 second cooldown per target).",
		["tier"] = "Gold",
	},
	["Salvation"] = {
		["description"] = "Upon dropping below {{as|50% of your '''maximum''' health}}, you unleash a shockwave that expands from your location over 1200 units, dealing {{pp|100 to 500|color=magic damage}} {{as|(+ 125% '''bonus''' AD)}} {{as|(+ 75% AP)}} {{as|magic damage}} to enemies hit and {{tip|heal|healing}} you and allied champions hit for {{pp|200 to 550}} {{as|(+ 200% '''bonus''' AD)}} {{as|(+ 120% AP)}} (90 second cooldown). Enemy champions hit within the first 600 units of the shockwave are {{tip|airborne|knocked back}} {{pp|450 to 100|0 to 600 for 11|type=distance travelled|label1=shockwave distance travelled}} units.",
		["tier"] = "Gold",
		["notes"] = [=[
		* This effect will still trigger if damage is taken while below {{as|50% '''maximum''' health}}.
        ]=]		
	},
	["Armored Impact"] = {
		["description"] = "After casting an ability, your next basic attack {{tip|on-hit}} within 10 seconds is empowered to deal {{pp|25 to 125|color=physical damage}} {{as|(+ 220% '''bonus''' armor)}} {{as|'''bonus''' physical damage}} to the target and surrounding enemies.",
		["tier"] = "Gold",
	},
	["Blue Barrier"] = {
		["description"] = "Gain a {{tip|shield}} equal to {{as|{{pp|200 to 450|key=%}} of mana spent}} for {{fd|1.5}} seconds. Shields can stack between multiple triggers of this effect, though not refreshing the duration of previous shields. Each shield instance is capped at a strength of {{pp|300 to 800}}.",
		["tier"] = "Silver",		
	},
	["Hands off the Talent"] = {
		["description"] = "Basic attacks against enemies hit farther than {{sti|75% of your '''total''' attack range}} deal {{as|15% '''bonus''' AD}} {{as|(+ 20% AP)}} {{as|'''bonus''' physical damage}}.",
		["tier"] = "Silver",
	},
	["Mosh Monster"] = {
		["description"] = "Casting your ultimate ability grants you {{as|{{pp|300 to 750}} '''bonus''' health}} on-cast and {{tip|slow|slows}} enemies within 350 units of you by 50% while it is active. Additionally, scoring a {{tip|takedown}} against an enemy champion permanently increases the {{as|'''bonus''' health}} gained by {{pp|15 to 30|color=health}} and expands the radius of the slow<!--by what amount?-->, tripled if the takedown was scored while your ultimate was active.",
		["tier"] = "Prismatic",
	},
	["Ultimate Recursion"] = {
		["description"] = "Gain 50 ultimate haste.",
		["tier"] = "Silver",
	},
	["Tickle Monster"] = {
		["description"] = "Convert '''all''' of your {{as|'''bonus''' attack damage}} into {{as|'''bonus''' attack speed}} at a rate of {{as|{{fd|1.75}}% '''bonus''' attack speed}} per {{as|1 '''bonus''' attack damage}}. Additionally, your basic attacks deal {{as|{{pp|5 to 50}} '''bonus''' magic damage}} {{tip|on-hit}}.",
		["tier"] = "Gold",
	},
	["No Mana, No Problem"] = {
		["description"] = "Convert '''all''' of the {{as|mana}} you gain from items into {{as|ability power}} at a rate of {{as|{{fd|0.8}} ability power}} per {{as|10 mana from items}}. Additionally, increase your {{as|ability power by 15%}}.",
		["tier"] = "Silver",
	},
	["Gift of the Drowned"] = {
		["description"] = "Convert '''all''' of your {{as|'''bonus''' health}} into {{as|lethality}} at a rate of{{ft|{{as|{{fd|0.05}} lethality}} per {{as|1 '''bonus''' health}}.|{{as|5 lethality}} per {{as|100 '''bonus''' health}}.}}Additionally, gain {{as|{{pp|10 to 25}} lethality}}.",
		["tier"] = "Silver",		
	},
	["Brass Blast"] = {
		["description"] = "Replace a summoner spell with ''{{si|Brass Blast}}''.<br><br>[[File:Brass Blast.png|20px|link=]] {{sbc|Brass Blast -}} {{#invoke:SpellData|geteffect|Brass Blast}}",
		["tier"] = "Gold",
		["notes"] = [=[
		* '''Brass Blast''' uses quick casting by default, which requires the active to be held and the recast to occur on release.
		* The cone has an initial radius of 700 units.
		* Knock back speed is 1300.
        ]=]		
    },
	["Recoil"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering it to deal 25% increased damage and on-cast cause you to {{tip|dash}} 450 units opposite the direction you are facing.",
		["tier"] = "Gold",
		["notes"] = [=[
		* Dash speed is 1500.
        ]=]
    },
	["The Boom and the Bass"] = {
		["description"] = "After casting an ability, your next basic attack {{tip|on-hit}} within 6 seconds is empowered to gain {{as|200% '''bonus''' attack speed}}, deal {{as|{{rd|50 to 200|25 to 100|pp=true}}|magic damage}} {{as|(+ {{rd|50%|25%}} '''bonus''' AD)}} {{as|(+ {{rd|30%|15%}} AP)}} {{as|'''bonus''' magic damage}}, and grant you {{as|{{pp|75 to 150|key=%}} '''bonus''' movement speed}} decaying over 2 seconds.",
		["tier"] = "Gold",
	},
	["Totentanz"] = {
		["description"] = "Replace a summoner spell with ''{{si|A Dance with Death}}''.<br><br>[[File:A Dance with Death.png|20px|link=]] {{sbc|A Dance with Death:}} {{#invoke:SpellData|geteffect|A Dance with Death}}",
		["tier"] = "Prismatic",
		["notes"] = [=[
		* The health threshold cannot be {{tt|modified|By increases or decreases to maximum health}} nor {{tt|exceeded|By healing and health regeneration}} by any means.
		* The pull towards the rift is a forced displacement.
		* While being pulled into the rift, the champion is rendered {{tip|untargetable}} and {{tip|lockout|unable to act}}.
        ]=]		
    },
	["Flow of Spirit"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering its cast to grant you {{as|{{pp|60 to 120|key=%}} {{as|'''bonus''' attack speed}}}} for 4 seconds.",
		["tier"] = "Gold",
    },
	["BEES!!!"] = {
		["description"] = "Hitting an enemy champion with an ability causes you to toss a beehive at their location (at the time of the hit) over {{fd|1.1}} seconds, which upon arrival explodes in a 425 radius to swarm enemy champions hit with bees for 2 seconds ({{pp|15 to 10}} second cooldown). While being swarmed, targets are dealt{{ft|{{pp|75 to 140|color=magic damage}} {{as|(+ 150% '''bonus''' AD)}} {{as|(+ 70% AP)}} {{as|magic damage}}|{{pp|75/4 to 140/4|color=magic damage}} {{as|(+ {{ap|150/4}}% '''bonus''' AD)}} {{as|(+ {{ap|70/4}}% AP)}} {{as|magic damage}} every {{fd|0.5}} seconds}}over the duration, applied {{tip|on-hit}} effects at 40% effectiveness every {{fd|0.5}} seconds (4 times total), and are {{tip|slow|slowed}} by 20%.",
		["tier"] = "Gold",
		["notes"] = [=[
        * The damage dealt by this augment counts as {{tip|persistent area damage}}, thus it is able to trigger {{tip|spell effects}}.
        ]=]		
    },
	["CRIMSON COBALT"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}}, empowering it to mark enemy champions damaged for 4 seconds. Your next basic attack {{tip|on-hit}} against a marked target consumes the mark to deal {{pp|100 to 250|color=magic damage}} {{as|(+ 70% '''bonus''' AD)}} {{as|(+ 35% AP)}} {{as|'''bonus''' magic damage}} and reduce the upgraded ability's '''current''' cooldown by 65% of its total cooldown.",
		["tier"] = "Gold",
    },
	["Lich Brain"] = {
		["description"] = "Gain {{as|30|ap}} {{as|(+ 4% '''bonus''' health)}} {{as|ability power}}.",
		["tier"] = "Silver",		
    },
	["Take'em Down Down Down"] = {
		["description"] = "Basic attacks {{tip|on-hit}} and ability hits against enemy champions apply a stack for 5 seconds, refreshing on subsequent applications and stacking up to 5 times, and deal {{as|{{rd|5 to 30|2.5 to 15|pp=true}}|magic damage}} {{as|(+ {{rd|35%|{{fd|17.5}}%}} '''bonus''' AD)}} {{as|(+ {{rd|15%|{{fd|7.5}}%}} AP)}} {{as|'''bonus''' magic damage}} plus {{as|{{rd|1 to 6|0.5 to 3|pp=true}}|magic damage}} {{as|(+ {{rd|7%|{{fd|3.5}}%}} '''bonus''' AD)}} {{as|(+ {{rd|3%|{{fd|1.5}}%}} AP)}} {{as|'''additional''' magic damage|magic damage}} per stack on the target.<!--additional DMG based on stacks calculated before or after the number of stacks on the target?--><br><br>The fifth stack against a target consumes them all to deal {{as|'''additional''' magic damage|magic damage}} equal to {{as|{{rd|17%|{{ap|17/2}}%}} of the target's '''missing''' health}} and {{tip|heal}} you for {{rd|67%|{{fd|33.5}}%}} of the {{tt|post-mitigation damage|Damage calculated after modifiers}} dealt.",
		["tier"] = "Gold",		
    },
	["Arcane Axiom"] = {
		["description"] = "Scoring a {{tip|takedown}} against an enemy champion within 3 seconds of damaging them refunds {{pp|15 to 30|key=%}} of your ultimate ability's '''total''' cooldown.",
		["tier"] = "Gold",		
    },
	["Fruitify"] = {
		["description"] = "Enemy champions that you score a {{tip|takedown}} against drop {{pp|3;4;5;6|1;7;11;15}} {{ui|Honeyfruit}} at the location of their death for 10 seconds. You and allied champions can step over a {{ui|Honeyfruit}} to consume it, {{tip|heal|healing}} for {{as|6% of '''maximum''' health}} and restoring {{as|6% of '''maximum''' mana}} as well as 10 {{as|energy}} and {{as|Fury}} (if applicable).",
		["tier"] = "Silver",		
    },
	["Jeweled Bracelet"] = {
		["description"] = "Your ultimate ability can now {{tip|critically strike}} for (145% + {{sti|{{as|'''bonus''' critical strike damage}}}}) damage. Additionally, gain {{as|25% critical strike chance}}.",
		["tier"] = "Gold",
		["notes"] = [=[
        * ''Jeweled Bracelet'' has no effect if the damage of the ultimate ability can already critically strike.
        ]=]		
    },
	["Lonely Warrior"] = {
		["description"] = "For each enemy champion within 600 units of you, gain {{as|15% '''bonus''' attack speed}} and 10 {{as|'''bonus''' armor}} and {{as|'''bonus''' magic resistance}}.",
		["tier"] = "Silver",		
    },
	["Sap Magic"] = {
		["description"] = "Your next basic attack {{tip|on-hit}} is empowered to deal {{pp|80 to 300|color=physical damage}} {{as|(+ 5% '''bonus''' health)}} {{as|'''bonus''' physical damage}} and {{tip|heal}} you for {{pp|50 to 250}} {{as|(+ 8% '''maximum''' health)}} (20 second cooldown). Casting an ability reduces the cooldown of this effect by 3 seconds.",
		["tier"] = "Gold",
    },
	["Still Here"] = {
		["description"] = "Gain {{pp|key=%|key1=%|type='''missing''' health|0 to 200 for 11|0 to 100|showtype=false|color=attack speed}} {{as|(based on your '''missing''' health)}} {{as|'''bonus''' attack speed}} and {{pp|key=%|key1=%|type='''missing''' health|0 to 35 for 11|0 to 100|showtype=false|color=life steal}} {{as|(based on your '''missing''' health)}} {{as|life steal}}.",
		["tier"] = "Gold",
    },
	["Heavy Is The Crown"] = {
		["description"] = "Your {{as|'''total''' movement speed}} is now reduced by 5% after {{fd|1.5}} seconds of entering combat. In return, you gain {{as|10 '''bonus''' attack damage}} and {{as|25 ability power}}, and your {{as|'''bonus''' attack damage}}, {{as|ability power}}, and {{as|'''total''' attack speed}} are increased by 10%. The movement speed reduction is removed after 7 seconds of being out of combat.<br><br>Scoring a {{tip|takedown}} against an enemy champion generates a stack of ''Burden''. For each stack, the {{as|'''bonus''' attack damage}}, {{as|ability power}}, and {{as|'''total''' attack speed}} are increased by 5%, and the {{as|'''total''' movement speed}} reduction is increased by {{as|{{fd|2.5%}}|ms}}. The movement speed reduction is capped at {{as|50%|ms}}. Lose 50% of stacks on death.",
		["tier"] = "Gold",		
    },
	["Group Hug"] = {
		["description"] = "Upgrades one of your champion's {{tip|ability|abilities}} that can target allied champions and has a {{tip|heal}} or {{tip|shield}} effect, empowering the ability's cast to also target two of the closest allied champions within 500 units of the primary target.",
		["tier"] = "Prismatic",
    },
	["Upgrade Stormsurge"] = {
		["description"] = "Upgrades {{ii|Stormsurge}}, empowering {{nie|Squall}} to strike the area around the primary target with lightning (350 radius) after its delay, dealing {{as|magic damage}} equal to {{as|10%|hp}} {{as|(+ 2% per 100 AP)}} {{as|of the target's '''maximum''' health}} to enemies hit. Enemy champions hit by the blast are also inflicted with ''Squall'', causing lightning to strike the area around them after the same delay, dealing the same damage. Subsequent blasts from these secondary targets do not inflict ''Squall'' to champions hit. Additionally, gain {{g|500}}.<br><br>''Squall's electric field from the target dying before the lightning strike does '''not''' apply this augment's effects.''",
		["tier"] = "Gold",
		["notes"] = [=[
		* The item upgrade is permanent and is not lost if this augment is removed or replaced.
        ]=]	
    },
	["Enchanting Butterflies"] = {
		["description"] = "{{tip|Heal|Healing}} or {{tip|shield|shielding}} an allied champion causes a ''Butterfly'' to gather around you, up to 7. After collecting 7 ''Butterflies'', your next instance of damage against an enemy champion fires all of your ''Butterflies'' at them, with the first one dealing {{pp|50 to 100|color=magic damage}} {{as|(+ 10% AP)}} {{as|(+ 1% '''bonus''' health)}} {{as|(+ 3 per 1% heal and shield power)}} {{as|magic damage}} and all subsequent ''Butterflies'' dealing{{ft|75% damage,|{{pp|50*0.75 to 100*0.75|color=magic damage}} {{as|(+ {{ap|10*0.75}}% AP)}} {{as|(+ {{ap|1*0.75}}% '''bonus''' health)}} {{as|(+ {{ap|3*0.75}} per 1% heal and shield power)}} {{as|magic damage}},}}for a total damage of {{pp|50+(50*0.75*6) to 100+(100*0.75*6)|color=magic damage}} {{as|(+ {{ap|10+10*0.75*6}}% AP)}} {{as|(+ {{ap|1+1*0.75*6}}% '''bonus''' health)}} {{as|(+ {{ap|3+3*0.75*6}} per 1% heal and shield power)}}.",
		["tier"] = "Gold",
		["notes"] = [=[
		* The ''Butteflies'' will orbit in a 150 radius around you.
        ]=]
    },
	["Pentakill: HEAVY"] = {
		["description"] = "Your champion's first basic ability ''(Q)'' gains {{as|20 ability haste}} and 10% increased damage, {{tip|heal|healing}}, and {{tip|shield|shielding}}.",
		["tier"] = "Gold",
    },
	["Pentakill: POWER"] = {
		["description"] = "Your champion's second basic ability ''(W)'' gains {{as|20 ability haste}} and 10% increased damage, {{tip|heal|healing}}, and {{tip|shield|shielding}}.",
		["tier"] = "Gold",
    },
	["Pentakill: THRASH"] = {
		["description"] = "Your champion's third basic ability ''(E)'' gains {{as|20 ability haste}} and 10% increased damage, {{tip|heal|healing}}, and {{tip|shield|shielding}}.",
		["tier"] = "Gold",
    },
	["Pentakill: DOOM"] = {
		["description"] = "Your champion's ultimate ability gains {{as|20 ability haste}} and 10% increased damage, {{tip|heal|healing}}, and {{tip|shield|shielding}}.",
		["tier"] = "Gold",		
    },
	["One Hit Wonder"] = {
		["description"] = "The cooldown of one of your champion's {{tip|ability|abilities}} is no longer affected by {{as|ability haste}}. In return, that ability now deals {{fd|7.5}}% increased damage per {{as|10 ability haste}} you have.",
		["tier"] = "Gold",
		["notes"] = [=[
		* The cooldown of the ability can still be reduced by basic ability haste as well as augments that grant haste on them — either on a exclusive or specific basis — which includes the following augments: [[File:Bread And Butter mayhem augment.png|20px|link=]] ''Bread and Butter/Cheese/Jam'', <br>[[File:Dashing mayhem augment.png|20px|link=]] ''Dashing'', [[File:Pursuit of Haste mayhem augment.png|20px|link=]] ''Pursuit of Haste'', [[File:Pentakill DOOM mayhem augment.png|20px|link=]] ''Pentakill: DOOM/HEAVY/POWER/THRASH'', and [[File:Dashing mayhem augment.png|20px|link=]] ''Spin to Win''.
		** These same sources of haste will also not count for the damage increase ratio.
        ]=]
    },
	["RISE"] = {
		["description"] = "Your ultimate ability now gains a recast for 5 seconds if an enemy champion dies shortly after being damaged by the spell. This may occur up to 2 times from the ultimate's initial cast, for a total of two recasts. The recast mimics the active effects of the ultimate ability as it was initially cast, but causes it to also deal 25% more damage than the previous cast.",
		["tier"] = "Prismatic",
    },    
	["Weapon of Destiny"] = {
		["description"] = "Upon acquiring this augment, the first eligible [[Legendary item]] in your inventory is granted the ''Weapon of Destiny'' passive effect.<br><br>{{sbc|Weapon of Destiny:}} Scoring a {{tip|takedown}} against an enemy champion within 3 seconds of damaging them permanently increases the [[Gold efficiency (League of Legends)|gold value]] of all {{tt|upgradeable stats|See notes}} on this item by exactly {{g|200}}, shared equally among them. This item can no longer be sold.<br><br>''Weapon of Destiny scans each item slot in your inventory (from slots 1-6) for an eligible Legendary item, granting the passive effect to the first eligible item that is found.''",
		["tier"] = "Gold",
		["notes"] = [=[
		* Statistics' gold value and eligible stats to be increased for the item:
		** {{g|50}} per 1 point of {{sti|{{as|ability haste}}}}.
		** {{g|20}} per 1 point of {{sti|{{as|ability power}}}}.
		** {{g|33.{{recurring|3}}}} per 1 point of {{sti|{{as|attack damage}}}}.
		** {{g|25}} per 1% of {{sti|{{as|attack speed}}}}.
		** {{g|20}} per 1 point of {{sti|{{as|armor}}}}.
		** {{g|20}} per 1 point of {{sti|{{as|magic resistance}}}}.
		** {{g|40}} per 1% of {{sti|{{as|critical strike chance}}}}.
		** {{g|166.{{recurring|6}}}} per 1% of {{sti|{{as|critical strike damage}}}}.
		** {{g|50}} per 1 point of {{sti|{{as|lethality}}}}.
		** {{g|66.{{recurring|6}}}} per 1 point of {{sti|{{as|flat magic penetration}}}}.
		** {{g|66.{{recurring|6}}}} per 1% of {{sti|{{as|percentage armor penetration}}}}.
		** {{g|111.{{recurring|1}}}} per 1% of {{sti|{{as|percentage magic penetration}}}}.
		** {{g|40}} per 1% of {{sti|{{as|life steal}}}}.
		** {{g|40}} per 1% of {{sti|{{as|omnivamp}}}}.
		** {{g|66.{{recurring|6}}}} per 1% of {{sti|{{as|percentage movement speed}}}}.
		** {{g|50}} per 1% of {{sti|{{as|heal and shield power}}}}.
		** {{g|2.{{recurring|6}}}} per 1 point of {{sti|{{as|health}}}}.
		** {{g|1}} per 1 point of {{sti|{{as|mana}}}}.
		* ''Weapon of Destiny's'' interaction with the [[File:Quest Wooglet's Witchcap mayhem augment.png|20px|link=]] Quest: Wooglet's Witchcap augment:
		** If ''Weapon of Destiny'' upgrades {{ii|Rabadon's Deathcap}} or {{ii|Zhonya's Hourglass}}, and the quest is completed afterward, the upgrade is not transferred to {{ii|Wooglet's Witchcap}} as it is not a Legendary item. Instead, the number of takedowns/stat upgrades from the previously upgraded item is stored and the upgrade is transferred to the first eligible Legendary item in the inventory, or to the next Legendary item that is purchased if none are available.
		* {{Pending for test}} ''Weapon of Destiny's'' interaction with the [[File:Quest Icathia's Fall mayhem augment.png|20px|link=]] Quest: Icathia's Fall and [[File:Quest Urf's Champion mayhem augment.png|20px|link=]] Quest: Urf's Champion augments.
        ]=]		
    },    
	["Bouncing Bees"] = {
		["description"] = "After casting an ability, your next basic attack is empowered to bounce a bee from the primary target to the nearest enemy champion within 700 units of them, dealing {{as|{{pp|50 to 100|key=%}} of the triggering attack's damage}} upon arrival.<br><br>Additionally, you are assigned with quests that require you to bounce bees onto enemy champions a number of times. There are three quest tiers, and each completed tier rewards you with {{as|'''bonus''' attack damage}} and an additional bee bounce on the empowered attack that repeats from the new target with each bounce, forming a chain of bee attacks.",
		["tier"] = "Prismatic",		
		["questinfo"] = [=[
{| class="article-table"
!Tier
! style="width: 200px;" | <center>Quest</center>
! style="width: 300px;" | Reward
|-
| <center>1</center>
|Bounce bees onto enemy champions 10 times.
|<center>Gain {{as|30 '''bonus''' attack damage}} and an additional bee bounce.<br>(2 bounces total)</center>
|-
| <center>2</center>
|Bounce bees onto enemy champions 30 more times (40 bounces total).
|<center>Gain {{as|30 '''bonus''' attack damage}} and an additional bee bounce.<br>(total {{as|60 '''bonus''' attack damage}} and 3 bounces)</center>
|-
| <center>3</center>
|Bounce bees onto enemy champions 123 more times (163 bounces total).
|<center>Gain {{as|30 '''bonus''' attack damage}} and an additional bee bounce.<br>(total {{as|90 '''bonus''' attack damage}} and 4 bounces)</center>
|}
        ]=]	
	},		
	["Pressure Cooker"] = {
		["description"] = "Surrounds you in flames, causing you to apply a {{as|Burn}} every second to enemy champions within 300 units for 3 seconds that deals {{as|magic damage}} equal to{{ft|{{as|{{fd|0.5}}% of your '''maximum''' health}} per second.|{{as|{{fd|1.5}}% of your '''maximum''' health}} over the duration.}}This {{as|Burn}} stacks infinitely and refreshes with each application.<br><br>Additionally, you are assigned with quests that require you to deal a certain amount of damage with the {{as|Burn}} effect against enemy champions. There are three quest tiers, and each completed tier grants you a reward that improves ''Pressure Cooker's'' effect.",
		["tier"] = "Gold",
		["questinfo"] = [=[
{| class="article-table"
!Tier
! style="width: 300px;" | <center>Quest</center>
! style="width: 300px;" | Reward
|-
| <center>1</center>
|Deal a total of 1500 damage with the {{as|Burn}}.
|Increase the {{as|Burn's}} range to 500 units.
|-
| <center>2</center>
|Deal an additional total of 12,000 damage with the {{as|Burn}} (13,500 damage total).
|Double the rate at which the {{as|Burn}} is inflicted, applying two stacks of the effect to targets every second.
|-
| <center>3</center>
|Deal an additional total of 15,000 damage with the {{as|Burn}} (28,500 damage total).
|Increase the {{as|Burn's}} range to 600 units.
|}
        ]=]		
	}
}
-- </pre>
-- [[Category:Lua]]