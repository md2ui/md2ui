# Material Design Icons md2ui

The emoji and symbols an agent writes, each with the Material Symbols icon that draws it.
`scripts/build_icon_font.py` turns this table into `material-design-icons-md2ui.ttf`, a font
in which every emoji draws as its icon. A theme that wants icons names that font as its
emoji `Font:` under `## Emoji styles`; the document keeps its emoji.

NOTICE: `material-design-icons-md2ui.ttf` is a modified version of Material Symbols Outlined
by Google, under the Apache License 2.0 (`LICENSE`): its icons are subset, rescaled and
remapped to emoji codepoints, and the family is renamed.

## Reading the table

- **Codepoints** are the characters, in hex, as Unicode's `emoji-test.txt` lists them. A row of
  several codepoints is a sequence (a keycap, a ZWJ emoji) drawn as one icon. A U+FE0F in a
  row is optional: the sequence also draws without it.
- **Icon** is a Material Symbols name (`assets/icons/source/*.codepoints`). A bare name keeps
  every axis variable, so the theme decides its fill and weight. `:filled` or `:outlined`
  pins the fill and keeps the other axes, so two characters can tell one icon apart
  (`★` filled, `☆` outlined).
  `:mirrored`, alone or after a pin, generates the icon's outline flipped left to right, for a
  character Material has no icon facing its way (`◀️` is `play_arrow:filled:mirrored`).
- **Char** and **Name** are for the reader; the build reads only Codepoints and Icon.

These need no row; the build adds them:

- every flag, a regional-indicator pair or a tag sequence, and a lone regional indicator,
  draws as `flag`;
- an emoji with a skin tone draws as the same emoji without one, and a lone skin tone as
  `square`;
- the joiner U+200D, U+FE0F, the keycap mark U+20E3 and the tag characters draw nothing;
- an emoji this table does not list draws as `square`, and a sequence it does not list as
  its first character's icon; the build prints how many of each it filled in. A character
  that only appears inside a sequence (a keycap's digit) draws as `square` on its own.

## Rebuilding

```sh
uv run python scripts/build_icon_font.py
```

It needs the source font in `assets/icons/source/`, which is not committed; when it is
missing the script prints where to download it.

| Char | Codepoints | Name | Icon |
|---|---|---|---|
| 😀 | 1F600 | grinning face | sentiment_very_satisfied |
| 😃 | 1F603 | grinning face with big eyes | sentiment_very_satisfied |
| 😄 | 1F604 | grinning face with smiling eyes | sentiment_very_satisfied |
| 😁 | 1F601 | beaming face with smiling eyes | sentiment_very_satisfied |
| 😆 | 1F606 | grinning squinting face | sentiment_very_satisfied |
| 😅 | 1F605 | grinning face with sweat | sentiment_stressed |
| 🤣 | 1F923 | rolling on the floor laughing | sentiment_very_satisfied |
| 😂 | 1F602 | face with tears of joy | sentiment_very_satisfied |
| 🙂 | 1F642 | slightly smiling face | sentiment_satisfied |
| 🙃 | 1F643 | upside-down face | sentiment_satisfied |
| 🫠 | 1FAE0 | melting face | sentiment_stressed |
| 😉 | 1F609 | winking face | sentiment_satisfied |
| 😊 | 1F60A | smiling face with smiling eyes | sentiment_content |
| 😇 | 1F607 | smiling face with halo | sentiment_content |
| 🥰 | 1F970 | smiling face with hearts | favorite |
| 😍 | 1F60D | smiling face with heart-eyes | favorite |
| 🤩 | 1F929 | star-struck | sentiment_very_satisfied |
| 😘 | 1F618 | face blowing a kiss | sentiment_content |
| 😗 | 1F617 | kissing face | sentiment_content |
| ☺️ | 263A FE0F | smiling face | sentiment_content |
| 😚 | 1F61A | kissing face with closed eyes | sentiment_content |
| 😙 | 1F619 | kissing face with smiling eyes | sentiment_content |
| 🥲 | 1F972 | smiling face with tear | sentiment_stressed |
| 😋 | 1F60B | face savoring food | sentiment_very_satisfied |
| 😛 | 1F61B | face with tongue | sentiment_excited |
| 😜 | 1F61C | winking face with tongue | sentiment_excited |
| 🤪 | 1F92A | zany face | sentiment_satisfied |
| 😝 | 1F61D | squinting face with tongue | sentiment_excited |
| 🤑 | 1F911 | money-mouth face | savings |
| 🤗 | 1F917 | smiling face with open hands | sentiment_neutral |
| 🤭 | 1F92D | face with hand over mouth | volume_off |
| 🫢 | 1FAE2 | face with open eyes and hand over mouth | visibility |
| 🫣 | 1FAE3 | face with peeking eye | visibility |
| 🤫 | 1F92B | shushing face | volume_off |
| 🤔 | 1F914 | thinking face | psychology |
| 🫡 | 1FAE1 | saluting face | face_nod |
| 🤐 | 1F910 | zipper-mouth face | volume_off |
| 🤨 | 1F928 | face with raised eyebrow | psychology |
| 😐 | 1F610 | neutral face | sentiment_neutral |
| 😑 | 1F611 | expressionless face | sentiment_neutral |
| 😶 | 1F636 | face without mouth | sentiment_neutral |
| 🫥 | 1FAE5 | dotted line face | visibility_off |
| 😶‍🌫️ | 1F636 200D 1F32B FE0F | face in clouds | visibility_off |
| 😏 | 1F60F | smirking face | sentiment_satisfied |
| 😒 | 1F612 | unamused face | sentiment_dissatisfied |
| 🙄 | 1F644 | face with rolling eyes | sentiment_dissatisfied |
| 😬 | 1F62C | grimacing face | sentiment_stressed |
| 😮‍💨 | 1F62E 200D 1F4A8 | face exhaling | sentiment_stressed |
| 🤥 | 1F925 | lying face | sentiment_neutral |
| 🫨 | 1FAE8 | shaking face | sentiment_stressed |
| 🙂‍↔️ | 1F642 200D 2194 FE0F | head shaking horizontally | sentiment_stressed |
| 🙂‍↕️ | 1F642 200D 2195 FE0F | head shaking vertically | sentiment_stressed |
| 😌 | 1F60C | relieved face | sentiment_calm |
| 😔 | 1F614 | pensive face | sentiment_dissatisfied |
| 😪 | 1F62A | sleepy face | bedtime |
| 🤤 | 1F924 | drooling face | sentiment_satisfied |
| 😴 | 1F634 | sleeping face | bedtime |
| 🫩 | 1FAE9 | face with bags under eyes | sentiment_stressed |
| 😷 | 1F637 | face with medical mask | medical_mask |
| 🤒 | 1F912 | face with thermometer | device_thermostat |
| 🤕 | 1F915 | face with head-bandage | healing |
| 🤢 | 1F922 | nauseated face | sick |
| 🤮 | 1F92E | face vomiting | sick |
| 🤧 | 1F927 | sneezing face | sick |
| 🥵 | 1F975 | hot face | device_thermostat |
| 🥶 | 1F976 | cold face | ac_unit |
| 🥴 | 1F974 | woozy face | sick |
| 😵 | 1F635 | face with crossed-out eyes | sick |
| 😵‍💫 | 1F635 200D 1F4AB | face with spiral eyes | sick |
| 🤯 | 1F92F | exploding head | explosion |
| 🤠 | 1F920 | cowboy hat face | emoji_people |
| 🥳 | 1F973 | partying face | sentiment_very_satisfied |
| 🥸 | 1F978 | disguised face | masks |
| 😎 | 1F60E | smiling face with sunglasses | sentiment_satisfied |
| 🤓 | 1F913 | nerd face | psychology |
| 🧐 | 1F9D0 | face with monocle | psychology |
| 😕 | 1F615 | confused face | sentiment_dissatisfied |
| 🫤 | 1FAE4 | face with diagonal mouth | sentiment_dissatisfied |
| 😟 | 1F61F | worried face | sentiment_worried |
| 🙁 | 1F641 | slightly frowning face | sentiment_dissatisfied |
| ☹️ | 2639 FE0F | frowning face | sentiment_dissatisfied |
| 😮 | 1F62E | face with open mouth | sentiment_worried |
| 😯 | 1F62F | hushed face | sentiment_worried |
| 😲 | 1F632 | astonished face | sentiment_worried |
| 😳 | 1F633 | flushed face | sentiment_worried |
| 🥺 | 1F97A | pleading face | sentiment_sad |
| 🥹 | 1F979 | face holding back tears | sentiment_sad |
| 😦 | 1F626 | frowning face with open mouth | sentiment_worried |
| 😧 | 1F627 | anguished face | sentiment_worried |
| 😨 | 1F628 | fearful face | sentiment_worried |
| 😰 | 1F630 | anxious face with sweat | sentiment_stressed |
| 😥 | 1F625 | sad but relieved face | sentiment_sad |
| 😢 | 1F622 | crying face | sentiment_sad |
| 😭 | 1F62D | loudly crying face | sentiment_sad |
| 😱 | 1F631 | face screaming in fear | sentiment_worried |
| 😖 | 1F616 | confounded face | sentiment_dissatisfied |
| 😣 | 1F623 | persevering face | sentiment_dissatisfied |
| 😞 | 1F61E | disappointed face | sentiment_dissatisfied |
| 😓 | 1F613 | downcast face with sweat | sentiment_stressed |
| 😩 | 1F629 | weary face | sentiment_extremely_dissatisfied |
| 😫 | 1F62B | tired face | sentiment_extremely_dissatisfied |
| 🥱 | 1F971 | yawning face | bedtime |
| 😤 | 1F624 | face with steam from nose | sentiment_extremely_dissatisfied |
| 😡 | 1F621 | enraged face | sentiment_extremely_dissatisfied |
| 😠 | 1F620 | angry face | sentiment_extremely_dissatisfied |
| 🤬 | 1F92C | face with symbols on mouth | sentiment_extremely_dissatisfied |
| 😈 | 1F608 | smiling face with horns | sentiment_extremely_dissatisfied |
| 👿 | 1F47F | angry face with horns | sentiment_extremely_dissatisfied |
| 💀 | 1F480 | skull | skull |
| ☠️ | 2620 FE0F | skull and crossbones | skull |
| 💩 | 1F4A9 | pile of poo | mood_bad |
| 🤡 | 1F921 | clown face | comedy_mask |
| 👹 | 1F479 | ogre | skeleton |
| 👺 | 1F47A | goblin | skeleton |
| 👻 | 1F47B | ghost | skeleton |
| 👽 | 1F47D | alien | skeleton |
| 👾 | 1F47E | alien monster | sports_esports |
| 🤖 | 1F916 | robot | smart_toy |
| 😺 | 1F63A | grinning cat | sentiment_very_satisfied |
| 😸 | 1F638 | grinning cat with smiling eyes | sentiment_very_satisfied |
| 😹 | 1F639 | cat with tears of joy | sentiment_very_satisfied |
| 😻 | 1F63B | smiling cat with heart-eyes | mood |
| 😼 | 1F63C | cat with wry smile | mood |
| 😽 | 1F63D | kissing cat | mood |
| 🙀 | 1F640 | weary cat | sentiment_worried |
| 😿 | 1F63F | crying cat | sentiment_sad |
| 😾 | 1F63E | pouting cat | sentiment_extremely_dissatisfied |
| 🙈 | 1F648 | see-no-evil monkey | visibility_off |
| 🙉 | 1F649 | hear-no-evil monkey | hearing_disabled |
| 🙊 | 1F64A | speak-no-evil monkey | voice_over_off |
| 💌 | 1F48C | love letter | mail |
| 💘 | 1F498 | heart with arrow | favorite |
| 💝 | 1F49D | heart with ribbon | heart_plus |
| 💖 | 1F496 | sparkling heart | favorite |
| 💗 | 1F497 | growing heart | favorite |
| 💓 | 1F493 | beating heart | favorite |
| 💞 | 1F49E | revolving hearts | favorite |
| 💕 | 1F495 | two hearts | favorite |
| 💟 | 1F49F | heart decoration | favorite |
| ❣️ | 2763 FE0F | heart exclamation | priority_high |
| 💔 | 1F494 | broken heart | heart_broken |
| ❤️‍🔥 | 2764 FE0F 200D 1F525 | heart on fire | local_fire_department |
| ❤️‍🩹 | 2764 FE0F 200D 1FA79 | mending heart | healing |
| ❤️ | 2764 FE0F | red heart | favorite:filled |
| 🩷 | 1FA77 | pink heart | favorite:filled |
| 🧡 | 1F9E1 | orange heart | favorite:filled |
| 💛 | 1F49B | yellow heart | favorite:filled |
| 💚 | 1F49A | green heart | favorite:filled |
| 💙 | 1F499 | blue heart | favorite:filled |
| 🩵 | 1FA75 | light blue heart | favorite:filled |
| 💜 | 1F49C | purple heart | favorite:filled |
| 🤎 | 1F90E | brown heart | favorite:filled |
| 🖤 | 1F5A4 | black heart | favorite:filled |
| 🩶 | 1FA76 | grey heart | favorite:filled |
| 🤍 | 1F90D | white heart | favorite:outlined |
| 💋 | 1F48B | kiss mark | lips |
| 💯 | 1F4AF | hundred points | percent |
| 💢 | 1F4A2 | anger symbol | priority_high |
| 💥 | 1F4A5 | collision | explosion |
| 💫 | 1F4AB | dizzy | auto_awesome |
| 💦 | 1F4A6 | sweat droplets | water_drop |
| 💨 | 1F4A8 | dashing away | air |
| 🕳️ | 1F573 FE0F | hole | radio_button_unchecked |
| 💬 | 1F4AC | speech balloon | chat_bubble |
| 👁️‍🗨️ | 1F441 FE0F 200D 1F5E8 FE0F | eye in speech bubble | forum |
| 🗨️ | 1F5E8 FE0F | left speech bubble | chat_bubble |
| 🗯️ | 1F5EF FE0F | right anger bubble | comment |
| 💭 | 1F4AD | thought balloon | cloud |
| 💤 | 1F4A4 | ZZZ | bedtime |
| 🐵 | 1F435 | monkey face | pets |
| 🐒 | 1F412 | monkey | pets |
| 🦍 | 1F98D | gorilla | pets |
| 🦧 | 1F9A7 | orangutan | pets |
| 🐶 | 1F436 | dog face | pets |
| 🐕 | 1F415 | dog | pets |
| 🦮 | 1F9AE | guide dog | pets |
| 🐕‍🦺 | 1F415 200D 1F9BA | service dog | pets |
| 🐩 | 1F429 | poodle | pets |
| 🐺 | 1F43A | wolf | pets |
| 🦊 | 1F98A | fox | pets |
| 🦝 | 1F99D | raccoon | pets |
| 🐱 | 1F431 | cat face | pets |
| 🐈 | 1F408 | cat | pets |
| 🐈‍⬛ | 1F408 200D 2B1B | black cat | pets |
| 🦁 | 1F981 | lion | pets |
| 🐯 | 1F42F | tiger face | pets |
| 🐅 | 1F405 | tiger | pets |
| 🐆 | 1F406 | leopard | pets |
| 🐴 | 1F434 | horse face | chess_knight |
| 🫎 | 1FACE | moose | pets |
| 🫏 | 1FACF | donkey | agriculture |
| 🐎 | 1F40E | horse | chess_knight |
| 🦄 | 1F984 | unicorn | auto_awesome |
| 🦓 | 1F993 | zebra | pets |
| 🦌 | 1F98C | deer | pets |
| 🦬 | 1F9AC | bison | pets |
| 🐮 | 1F42E | cow face | agriculture |
| 🐂 | 1F402 | ox | agriculture |
| 🐃 | 1F403 | water buffalo | agriculture |
| 🐄 | 1F404 | cow | agriculture |
| 🐷 | 1F437 | pig face | agriculture |
| 🐖 | 1F416 | pig | agriculture |
| 🐗 | 1F417 | boar | pets |
| 🐽 | 1F43D | pig nose | agriculture |
| 🐏 | 1F40F | ram | agriculture |
| 🐑 | 1F411 | ewe | agriculture |
| 🐐 | 1F410 | goat | agriculture |
| 🐪 | 1F42A | camel | pets |
| 🐫 | 1F42B | two-hump camel | pets |
| 🦙 | 1F999 | llama | agriculture |
| 🦒 | 1F992 | giraffe | pets |
| 🐘 | 1F418 | elephant | pets |
| 🦣 | 1F9A3 | mammoth | pets |
| 🦏 | 1F98F | rhinoceros | pets |
| 🦛 | 1F99B | hippopotamus | pets |
| 🐭 | 1F42D | mouse face | cruelty_free |
| 🐁 | 1F401 | mouse | pest_control_rodent |
| 🐀 | 1F400 | rat | pest_control_rodent |
| 🐹 | 1F439 | hamster | pest_control_rodent |
| 🐰 | 1F430 | rabbit face | cruelty_free |
| 🐇 | 1F407 | rabbit | cruelty_free |
| 🐿️ | 1F43F FE0F | chipmunk | cruelty_free |
| 🦫 | 1F9AB | beaver | pets |
| 🦔 | 1F994 | hedgehog | cruelty_free |
| 🦇 | 1F987 | bat | pest_control |
| 🐻 | 1F43B | bear | pets |
| 🐻‍❄️ | 1F43B 200D 2744 FE0F | polar bear | pets |
| 🐨 | 1F428 | koala | pets |
| 🐼 | 1F43C | panda | pets |
| 🦥 | 1F9A5 | sloth | pets |
| 🦦 | 1F9A6 | otter | pets |
| 🦨 | 1F9A8 | skunk | pets |
| 🦘 | 1F998 | kangaroo | pets |
| 🦡 | 1F9A1 | badger | pets |
| 🐾 | 1F43E | paw prints | pets |
| 🦃 | 1F983 | turkey | flutter_dash |
| 🐔 | 1F414 | chicken | flutter_dash |
| 🐓 | 1F413 | rooster | flutter_dash |
| 🐣 | 1F423 | hatching chick | egg_alt |
| 🐤 | 1F424 | baby chick | flutter_dash |
| 🐥 | 1F425 | front-facing baby chick | flutter_dash |
| 🐦 | 1F426 | bird | flutter_dash |
| 🐧 | 1F427 | penguin | flutter_dash |
| 🕊️ | 1F54A FE0F | dove | flutter_dash |
| 🦅 | 1F985 | eagle | flutter_dash |
| 🦆 | 1F986 | duck | flutter_dash |
| 🦢 | 1F9A2 | swan | flutter_dash |
| 🦉 | 1F989 | owl | owl |
| 🦤 | 1F9A4 | dodo | flutter_dash |
| 🪶 | 1FAB6 | feather | history_edu |
| 🦩 | 1F9A9 | flamingo | flutter_dash |
| 🦚 | 1F99A | peacock | flutter_dash |
| 🦜 | 1F99C | parrot | flutter_dash |
| 🪽 | 1FABD | wing | travel |
| 🐦‍⬛ | 1F426 200D 2B1B | black bird | raven |
| 🪿 | 1FABF | goose | flutter_dash |
| 🐦‍🔥 | 1F426 200D 1F525 | phoenix | local_fire_department |
| 🐸 | 1F438 | frog | emoji_nature |
| 🐊 | 1F40A | crocodile | emoji_nature |
| 🐢 | 1F422 | turtle | emoji_nature |
| 🦎 | 1F98E | lizard | emoji_nature |
| 🐍 | 1F40D | snake | emoji_nature |
| 🐲 | 1F432 | dragon face | pets |
| 🐉 | 1F409 | dragon | pets |
| 🦕 | 1F995 | sauropod | emoji_nature |
| 🦖 | 1F996 | T-Rex | emoji_nature |
| 🐳 | 1F433 | spouting whale | waves |
| 🐋 | 1F40B | whale | waves |
| 🐬 | 1F42C | dolphin | waves |
| 🦭 | 1F9AD | seal | waves |
| 🐟 | 1F41F | fish | set_meal |
| 🐠 | 1F420 | tropical fish | set_meal |
| 🐡 | 1F421 | blowfish | set_meal |
| 🦈 | 1F988 | shark | set_meal |
| 🐙 | 1F419 | octopus | set_meal |
| 🐚 | 1F41A | spiral shell | egg |
| 🪸 | 1FAB8 | coral | waves |
| 🪼 | 1FABC | jellyfish | waves |
| 🦀 | 1F980 | crab | set_meal |
| 🦞 | 1F99E | lobster | set_meal |
| 🦐 | 1F990 | shrimp | set_meal |
| 🦑 | 1F991 | squid | set_meal |
| 🦪 | 1F9AA | oyster | set_meal |
| 🐌 | 1F40C | snail | snail |
| 🦋 | 1F98B | butterfly | emoji_nature |
| 🐛 | 1F41B | bug | bug_report |
| 🐜 | 1F41C | ant | emoji_nature |
| 🐝 | 1F41D | honeybee | hive |
| 🪲 | 1FAB2 | beetle | emoji_nature |
| 🐞 | 1F41E | lady beetle | emoji_nature |
| 🦗 | 1F997 | cricket | emoji_nature |
| 🪳 | 1FAB3 | cockroach | bug_report |
| 🕷️ | 1F577 FE0F | spider | pest_control |
| 🕸️ | 1F578 FE0F | spider web | pest_control |
| 🦂 | 1F982 | scorpion | pest_control |
| 🦟 | 1F99F | mosquito | bug_report |
| 🪰 | 1FAB0 | fly | pest_control |
| 🪱 | 1FAB1 | worm | pest_control |
| 🦠 | 1F9A0 | microbe | coronavirus |
| 💐 | 1F490 | bouquet | local_florist |
| 🌸 | 1F338 | cherry blossom | filter_vintage |
| 💮 | 1F4AE | white flower | filter_vintage |
| 🪷 | 1FAB7 | lotus | filter_vintage |
| 🏵️ | 1F3F5 FE0F | rosette | filter_vintage |
| 🌹 | 1F339 | rose | local_florist |
| 🥀 | 1F940 | wilted flower | sword_rose |
| 🌺 | 1F33A | hibiscus | filter_vintage |
| 🌻 | 1F33B | sunflower | filter_vintage |
| 🌼 | 1F33C | blossom | filter_vintage |
| 🌷 | 1F337 | tulip | filter_vintage |
| 🪻 | 1FABB | hyacinth | filter_vintage |
| 🌱 | 1F331 | seedling | psychiatry |
| 🪴 | 1FAB4 | potted plant | potted_plant |
| 🌲 | 1F332 | evergreen tree | forest |
| 🌳 | 1F333 | deciduous tree | forest |
| 🌴 | 1F334 | palm tree | park |
| 🌵 | 1F335 | cactus | grass |
| 🌾 | 1F33E | sheaf of rice | grass |
| 🌿 | 1F33F | herb | grass |
| ☘️ | 2618 FE0F | shamrock | eco |
| 🍀 | 1F340 | four leaf clover | eco |
| 🍁 | 1F341 | maple leaf | eco |
| 🍂 | 1F342 | fallen leaf | eco |
| 🍃 | 1F343 | leaf fluttering in wind | eco |
| 🪹 | 1FAB9 | empty nest | nest_eco_leaf |
| 🪺 | 1FABA | nest with eggs | egg_alt |
| 🍄 | 1F344 | mushroom | compost |
| 🪾 | 1FABE | leafless tree | nature |
| 👋 | 1F44B | waving hand | waving_hand |
| 🤚 | 1F91A | raised back of hand | back_hand |
| 🖐️ | 1F590 FE0F | hand with fingers splayed | front_hand |
| ✋ | 270B | raised hand | front_hand |
| 🖖 | 1F596 | vulcan salute | sign_language |
| 🫱 | 1FAF1 | rightwards hand | pan_tool |
| 🫲 | 1FAF2 | leftwards hand | pan_tool |
| 🫳 | 1FAF3 | palm down hand | pan_tool |
| 🫴 | 1FAF4 | palm up hand | pan_tool |
| 🫷 | 1FAF7 | leftwards pushing hand | pan_tool |
| 🫸 | 1FAF8 | rightwards pushing hand | pan_tool |
| 👌 | 1F44C | OK hand | pinch |
| 🤌 | 1F90C | pinched fingers | pinch |
| 🤏 | 1F90F | pinching hand | pinch |
| ✌️ | 270C FE0F | victory hand | sign_language |
| 🤞 | 1F91E | crossed fingers | sign_language |
| 🫰 | 1FAF0 | hand with index finger and thumb crossed | favorite |
| 🤟 | 1F91F | love-you gesture | sign_language |
| 🤘 | 1F918 | sign of the horns | sign_language |
| 🤙 | 1F919 | call me hand | sign_language |
| 👈 | 1F448 | backhand index pointing left | arrow_back |
| 👉 | 1F449 | backhand index pointing right | arrow_forward |
| 👆 | 1F446 | backhand index pointing up | arrow_upward |
| 🖕 | 1F595 | middle finger | front_hand |
| 👇 | 1F447 | backhand index pointing down | arrow_downward |
| ☝️ | 261D FE0F | index pointing up | arrow_upward |
| 🫵 | 1FAF5 | index pointing at the viewer | touch_app |
| 👍 | 1F44D | thumbs up | thumb_up |
| 👎 | 1F44E | thumbs down | thumb_down |
| ✊ | 270A | raised fist | front_hand |
| 👊 | 1F44A | oncoming fist | front_hand |
| 🤛 | 1F91B | left-facing fist | front_hand |
| 🤜 | 1F91C | right-facing fist | front_hand |
| 👏 | 1F44F | clapping hands | volunteer_activism |
| 🙌 | 1F64C | raising hands | celebration |
| 🫶 | 1FAF6 | heart hands | volunteer_activism |
| 👐 | 1F450 | open hands | volunteer_activism |
| 🤲 | 1F932 | palms up together | volunteer_activism |
| 🤝 | 1F91D | handshake | handshake |
| 🙏 | 1F64F | folded hands | self_improvement |
| ✍️ | 270D FE0F | writing hand | edit |
| 💅 | 1F485 | nail polish | brush |
| 🤳 | 1F933 | selfie | camera_front |
| 💪 | 1F4AA | flexed biceps | fitness_center |
| 🦾 | 1F9BE | mechanical arm | fitness_center |
| 🦿 | 1F9BF | mechanical leg | footprint |
| 🦵 | 1F9B5 | leg | footprint |
| 🦶 | 1F9B6 | foot | footprint |
| 👂 | 1F442 | ear | hearing |
| 🦻 | 1F9BB | ear with hearing aid | hearing |
| 👃 | 1F443 | nose | face |
| 🧠 | 1F9E0 | brain | psychology |
| 🫀 | 1FAC0 | anatomical heart | cardiology |
| 🫁 | 1FAC1 | lungs | pulmonology |
| 🦷 | 1F9B7 | tooth | dentistry |
| 🦴 | 1F9B4 | bone | orthopedics |
| 👀 | 1F440 | eyes | visibility |
| 👁️ | 1F441 FE0F | eye | visibility |
| 👅 | 1F445 | tongue | mood |
| 👄 | 1F444 | mouth | mood |
| 🫦 | 1FAE6 | biting lip | mood |
| 👶 | 1F476 | baby | child_care |
| 🧒 | 1F9D2 | child | child_care |
| 👦 | 1F466 | boy | child_care |
| 👧 | 1F467 | girl | child_care |
| 🧑 | 1F9D1 | person | person |
| 👱 | 1F471 | person: blond hair | person |
| 👨 | 1F468 | man | man |
| 🧔 | 1F9D4 | person: beard | person |
| 🧔‍♂️ | 1F9D4 200D 2642 FE0F | man: beard | man |
| 🧔‍♀️ | 1F9D4 200D 2640 FE0F | woman: beard | woman |
| 👨‍🦰 | 1F468 200D 1F9B0 | man: red hair | man |
| 👨‍🦱 | 1F468 200D 1F9B1 | man: curly hair | man |
| 👨‍🦳 | 1F468 200D 1F9B3 | man: white hair | man |
| 👨‍🦲 | 1F468 200D 1F9B2 | man: bald | man |
| 👩 | 1F469 | woman | woman |
| 👩‍🦰 | 1F469 200D 1F9B0 | woman: red hair | woman |
| 🧑‍🦰 | 1F9D1 200D 1F9B0 | person: red hair | person |
| 👩‍🦱 | 1F469 200D 1F9B1 | woman: curly hair | woman |
| 🧑‍🦱 | 1F9D1 200D 1F9B1 | person: curly hair | person |
| 👩‍🦳 | 1F469 200D 1F9B3 | woman: white hair | woman |
| 🧑‍🦳 | 1F9D1 200D 1F9B3 | person: white hair | person |
| 👩‍🦲 | 1F469 200D 1F9B2 | woman: bald | woman |
| 🧑‍🦲 | 1F9D1 200D 1F9B2 | person: bald | person |
| 👱‍♀️ | 1F471 200D 2640 FE0F | woman: blond hair | woman |
| 👱‍♂️ | 1F471 200D 2642 FE0F | man: blond hair | man |
| 🧓 | 1F9D3 | older person | elderly |
| 👴 | 1F474 | old man | elderly |
| 👵 | 1F475 | old woman | elderly |
| 🙍 | 1F64D | person frowning | sentiment_dissatisfied |
| 🙍‍♂️ | 1F64D 200D 2642 FE0F | man frowning | sentiment_dissatisfied |
| 🙍‍♀️ | 1F64D 200D 2640 FE0F | woman frowning | sentiment_dissatisfied |
| 🙎 | 1F64E | person pouting | sentiment_dissatisfied |
| 🙎‍♂️ | 1F64E 200D 2642 FE0F | man pouting | sentiment_dissatisfied |
| 🙎‍♀️ | 1F64E 200D 2640 FE0F | woman pouting | sentiment_dissatisfied |
| 🙅 | 1F645 | person gesturing NO | do_not_disturb_on |
| 🙅‍♂️ | 1F645 200D 2642 FE0F | man gesturing NO | do_not_disturb_on |
| 🙅‍♀️ | 1F645 200D 2640 FE0F | woman gesturing NO | do_not_disturb_on |
| 🙆 | 1F646 | person gesturing OK | check_circle |
| 🙆‍♂️ | 1F646 200D 2642 FE0F | man gesturing OK | check_circle |
| 🙆‍♀️ | 1F646 200D 2640 FE0F | woman gesturing OK | check_circle |
| 💁 | 1F481 | person tipping hand | support_agent |
| 💁‍♂️ | 1F481 200D 2642 FE0F | man tipping hand | support_agent |
| 💁‍♀️ | 1F481 200D 2640 FE0F | woman tipping hand | support_agent |
| 🙋 | 1F64B | person raising hand | front_hand |
| 🙋‍♂️ | 1F64B 200D 2642 FE0F | man raising hand | front_hand |
| 🙋‍♀️ | 1F64B 200D 2640 FE0F | woman raising hand | front_hand |
| 🧏 | 1F9CF | deaf person | hearing_disabled |
| 🧏‍♂️ | 1F9CF 200D 2642 FE0F | deaf man | hearing_disabled |
| 🧏‍♀️ | 1F9CF 200D 2640 FE0F | deaf woman | hearing_disabled |
| 🙇 | 1F647 | person bowing | self_improvement |
| 🙇‍♂️ | 1F647 200D 2642 FE0F | man bowing | self_improvement |
| 🙇‍♀️ | 1F647 200D 2640 FE0F | woman bowing | self_improvement |
| 🤦 | 1F926 | person facepalming | sentiment_neutral |
| 🤦‍♂️ | 1F926 200D 2642 FE0F | man facepalming | sentiment_neutral |
| 🤦‍♀️ | 1F926 200D 2640 FE0F | woman facepalming | sentiment_neutral |
| 🤷 | 1F937 | person shrugging | sentiment_neutral |
| 🤷‍♂️ | 1F937 200D 2642 FE0F | man shrugging | sentiment_neutral |
| 🤷‍♀️ | 1F937 200D 2640 FE0F | woman shrugging | sentiment_neutral |
| 🧑‍⚕️ | 1F9D1 200D 2695 FE0F | health worker | medical_services |
| 👨‍⚕️ | 1F468 200D 2695 FE0F | man health worker | medical_services |
| 👩‍⚕️ | 1F469 200D 2695 FE0F | woman health worker | medical_services |
| 🧑‍🎓 | 1F9D1 200D 1F393 | student | school |
| 👨‍🎓 | 1F468 200D 1F393 | man student | school |
| 👩‍🎓 | 1F469 200D 1F393 | woman student | school |
| 🧑‍🏫 | 1F9D1 200D 1F3EB | teacher | school |
| 👨‍🏫 | 1F468 200D 1F3EB | man teacher | school |
| 👩‍🏫 | 1F469 200D 1F3EB | woman teacher | school |
| 🧑‍⚖️ | 1F9D1 200D 2696 FE0F | judge | gavel |
| 👨‍⚖️ | 1F468 200D 2696 FE0F | man judge | gavel |
| 👩‍⚖️ | 1F469 200D 2696 FE0F | woman judge | gavel |
| 🧑‍🌾 | 1F9D1 200D 1F33E | farmer | agriculture |
| 👨‍🌾 | 1F468 200D 1F33E | man farmer | agriculture |
| 👩‍🌾 | 1F469 200D 1F33E | woman farmer | agriculture |
| 🧑‍🍳 | 1F9D1 200D 1F373 | cook | skillet |
| 👨‍🍳 | 1F468 200D 1F373 | man cook | skillet |
| 👩‍🍳 | 1F469 200D 1F373 | woman cook | skillet |
| 🧑‍🔧 | 1F9D1 200D 1F527 | mechanic | build |
| 👨‍🔧 | 1F468 200D 1F527 | man mechanic | build |
| 👩‍🔧 | 1F469 200D 1F527 | woman mechanic | build |
| 🧑‍🏭 | 1F9D1 200D 1F3ED | factory worker | factory |
| 👨‍🏭 | 1F468 200D 1F3ED | man factory worker | factory |
| 👩‍🏭 | 1F469 200D 1F3ED | woman factory worker | factory |
| 🧑‍💼 | 1F9D1 200D 1F4BC | office worker | business_center |
| 👨‍💼 | 1F468 200D 1F4BC | man office worker | business_center |
| 👩‍💼 | 1F469 200D 1F4BC | woman office worker | business_center |
| 🧑‍🔬 | 1F9D1 200D 1F52C | scientist | science |
| 👨‍🔬 | 1F468 200D 1F52C | man scientist | science |
| 👩‍🔬 | 1F469 200D 1F52C | woman scientist | science |
| 🧑‍💻 | 1F9D1 200D 1F4BB | technologist | computer |
| 👨‍💻 | 1F468 200D 1F4BB | man technologist | computer |
| 👩‍💻 | 1F469 200D 1F4BB | woman technologist | computer |
| 🧑‍🎤 | 1F9D1 200D 1F3A4 | singer | mic |
| 👨‍🎤 | 1F468 200D 1F3A4 | man singer | mic |
| 👩‍🎤 | 1F469 200D 1F3A4 | woman singer | mic |
| 🧑‍🎨 | 1F9D1 200D 1F3A8 | artist | palette |
| 👨‍🎨 | 1F468 200D 1F3A8 | man artist | palette |
| 👩‍🎨 | 1F469 200D 1F3A8 | woman artist | palette |
| 🧑‍✈️ | 1F9D1 200D 2708 FE0F | pilot | flight |
| 👨‍✈️ | 1F468 200D 2708 FE0F | man pilot | flight |
| 👩‍✈️ | 1F469 200D 2708 FE0F | woman pilot | flight |
| 🧑‍🚀 | 1F9D1 200D 1F680 | astronaut | rocket_launch |
| 👨‍🚀 | 1F468 200D 1F680 | man astronaut | rocket_launch |
| 👩‍🚀 | 1F469 200D 1F680 | woman astronaut | rocket_launch |
| 🧑‍🚒 | 1F9D1 200D 1F692 | firefighter | local_fire_department |
| 👨‍🚒 | 1F468 200D 1F692 | man firefighter | local_fire_department |
| 👩‍🚒 | 1F469 200D 1F692 | woman firefighter | local_fire_department |
| 👮 | 1F46E | police officer | local_police |
| 👮‍♂️ | 1F46E 200D 2642 FE0F | man police officer | local_police |
| 👮‍♀️ | 1F46E 200D 2640 FE0F | woman police officer | local_police |
| 🕵️ | 1F575 FE0F | detective | search |
| 🕵️‍♂️ | 1F575 FE0F 200D 2642 FE0F | man detective | search |
| 🕵️‍♀️ | 1F575 FE0F 200D 2640 FE0F | woman detective | search |
| 💂 | 1F482 | guard | security |
| 💂‍♂️ | 1F482 200D 2642 FE0F | man guard | security |
| 💂‍♀️ | 1F482 200D 2640 FE0F | woman guard | security |
| 🥷 | 1F977 | ninja | security |
| 👷 | 1F477 | construction worker | engineering |
| 👷‍♂️ | 1F477 200D 2642 FE0F | man construction worker | engineering |
| 👷‍♀️ | 1F477 200D 2640 FE0F | woman construction worker | engineering |
| 🫅 | 1FAC5 | person with crown | crown |
| 🤴 | 1F934 | prince | crown |
| 👸 | 1F478 | princess | crown |
| 👳 | 1F473 | person wearing turban | person |
| 👳‍♂️ | 1F473 200D 2642 FE0F | man wearing turban | person |
| 👳‍♀️ | 1F473 200D 2640 FE0F | woman wearing turban | person |
| 👲 | 1F472 | person with skullcap | person |
| 🧕 | 1F9D5 | woman with headscarf | person |
| 🤵 | 1F935 | person in tuxedo | person |
| 🤵‍♂️ | 1F935 200D 2642 FE0F | man in tuxedo | person |
| 🤵‍♀️ | 1F935 200D 2640 FE0F | woman in tuxedo | person |
| 👰 | 1F470 | person with veil | person |
| 👰‍♂️ | 1F470 200D 2642 FE0F | man with veil | person |
| 👰‍♀️ | 1F470 200D 2640 FE0F | woman with veil | person |
| 🤰 | 1F930 | pregnant woman | pregnant_woman |
| 🫃 | 1FAC3 | pregnant man | pregnant_woman |
| 🫄 | 1FAC4 | pregnant person | pregnant_woman |
| 🤱 | 1F931 | breast-feeding | child_care |
| 👩‍🍼 | 1F469 200D 1F37C | woman feeding baby | child_care |
| 👨‍🍼 | 1F468 200D 1F37C | man feeding baby | child_care |
| 🧑‍🍼 | 1F9D1 200D 1F37C | person feeding baby | child_care |
| 👼 | 1F47C | baby angel | child_care |
| 🎅 | 1F385 | Santa Claus | celebration |
| 🤶 | 1F936 | Mrs. Claus | celebration |
| 🧑‍🎄 | 1F9D1 200D 1F384 | Mx Claus | celebration |
| 🦸 | 1F9B8 | superhero | security |
| 🦸‍♂️ | 1F9B8 200D 2642 FE0F | man superhero | security |
| 🦸‍♀️ | 1F9B8 200D 2640 FE0F | woman superhero | security |
| 🦹 | 1F9B9 | supervillain | security |
| 🦹‍♂️ | 1F9B9 200D 2642 FE0F | man supervillain | security |
| 🦹‍♀️ | 1F9B9 200D 2640 FE0F | woman supervillain | security |
| 🧙 | 1F9D9 | mage | auto_fix_high |
| 🧙‍♂️ | 1F9D9 200D 2642 FE0F | man mage | auto_fix_high |
| 🧙‍♀️ | 1F9D9 200D 2640 FE0F | woman mage | auto_fix_high |
| 🧚 | 1F9DA | fairy | auto_fix_high |
| 🧚‍♂️ | 1F9DA 200D 2642 FE0F | man fairy | auto_fix_high |
| 🧚‍♀️ | 1F9DA 200D 2640 FE0F | woman fairy | auto_fix_high |
| 🧛 | 1F9DB | vampire | skull |
| 🧛‍♂️ | 1F9DB 200D 2642 FE0F | man vampire | skull |
| 🧛‍♀️ | 1F9DB 200D 2640 FE0F | woman vampire | skull |
| 🧜 | 1F9DC | merperson | waves |
| 🧜‍♂️ | 1F9DC 200D 2642 FE0F | merman | waves |
| 🧜‍♀️ | 1F9DC 200D 2640 FE0F | mermaid | waves |
| 🧝 | 1F9DD | elf | park |
| 🧝‍♂️ | 1F9DD 200D 2642 FE0F | man elf | park |
| 🧝‍♀️ | 1F9DD 200D 2640 FE0F | woman elf | park |
| 🧞 | 1F9DE | genie | auto_fix_high |
| 🧞‍♂️ | 1F9DE 200D 2642 FE0F | man genie | auto_fix_high |
| 🧞‍♀️ | 1F9DE 200D 2640 FE0F | woman genie | auto_fix_high |
| 🧟 | 1F9DF | zombie | skull |
| 🧟‍♂️ | 1F9DF 200D 2642 FE0F | man zombie | skull |
| 🧟‍♀️ | 1F9DF 200D 2640 FE0F | woman zombie | skull |
| 🧌 | 1F9CC | troll | skull |
| 💆 | 1F486 | person getting massage | spa |
| 💆‍♂️ | 1F486 200D 2642 FE0F | man getting massage | spa |
| 💆‍♀️ | 1F486 200D 2640 FE0F | woman getting massage | spa |
| 💇 | 1F487 | person getting haircut | content_cut |
| 💇‍♂️ | 1F487 200D 2642 FE0F | man getting haircut | content_cut |
| 💇‍♀️ | 1F487 200D 2640 FE0F | woman getting haircut | content_cut |
| 🚶 | 1F6B6 | person walking | directions_walk |
| 🚶‍♂️ | 1F6B6 200D 2642 FE0F | man walking | directions_walk |
| 🚶‍♀️ | 1F6B6 200D 2640 FE0F | woman walking | directions_walk |
| 🚶‍➡️ | 1F6B6 200D 27A1 FE0F | person walking facing right | directions_walk |
| 🚶‍♀️‍➡️ | 1F6B6 200D 2640 FE0F 200D 27A1 FE0F | woman walking facing right | directions_walk |
| 🚶‍♂️‍➡️ | 1F6B6 200D 2642 FE0F 200D 27A1 FE0F | man walking facing right | directions_walk |
| 🧍 | 1F9CD | person standing | person |
| 🧍‍♂️ | 1F9CD 200D 2642 FE0F | man standing | person |
| 🧍‍♀️ | 1F9CD 200D 2640 FE0F | woman standing | person |
| 🧎 | 1F9CE | person kneeling | self_improvement |
| 🧎‍♂️ | 1F9CE 200D 2642 FE0F | man kneeling | self_improvement |
| 🧎‍♀️ | 1F9CE 200D 2640 FE0F | woman kneeling | self_improvement |
| 🧎‍➡️ | 1F9CE 200D 27A1 FE0F | person kneeling facing right | self_improvement |
| 🧎‍♀️‍➡️ | 1F9CE 200D 2640 FE0F 200D 27A1 FE0F | woman kneeling facing right | self_improvement |
| 🧎‍♂️‍➡️ | 1F9CE 200D 2642 FE0F 200D 27A1 FE0F | man kneeling facing right | self_improvement |
| 🧑‍🦯 | 1F9D1 200D 1F9AF | person with white cane | blind |
| 🧑‍🦯‍➡️ | 1F9D1 200D 1F9AF 200D 27A1 FE0F | person with white cane facing right | blind |
| 👨‍🦯 | 1F468 200D 1F9AF | man with white cane | blind |
| 👨‍🦯‍➡️ | 1F468 200D 1F9AF 200D 27A1 FE0F | man with white cane facing right | blind |
| 👩‍🦯 | 1F469 200D 1F9AF | woman with white cane | blind |
| 👩‍🦯‍➡️ | 1F469 200D 1F9AF 200D 27A1 FE0F | woman with white cane facing right | blind |
| 🧑‍🦼 | 1F9D1 200D 1F9BC | person in motorized wheelchair | accessible |
| 🧑‍🦼‍➡️ | 1F9D1 200D 1F9BC 200D 27A1 FE0F | person in motorized wheelchair facing right | accessible |
| 👨‍🦼 | 1F468 200D 1F9BC | man in motorized wheelchair | accessible |
| 👨‍🦼‍➡️ | 1F468 200D 1F9BC 200D 27A1 FE0F | man in motorized wheelchair facing right | accessible |
| 👩‍🦼 | 1F469 200D 1F9BC | woman in motorized wheelchair | accessible |
| 👩‍🦼‍➡️ | 1F469 200D 1F9BC 200D 27A1 FE0F | woman in motorized wheelchair facing right | accessible |
| 🧑‍🦽 | 1F9D1 200D 1F9BD | person in manual wheelchair | accessible |
| 🧑‍🦽‍➡️ | 1F9D1 200D 1F9BD 200D 27A1 FE0F | person in manual wheelchair facing right | accessible |
| 👨‍🦽 | 1F468 200D 1F9BD | man in manual wheelchair | accessible |
| 👨‍🦽‍➡️ | 1F468 200D 1F9BD 200D 27A1 FE0F | man in manual wheelchair facing right | accessible |
| 👩‍🦽 | 1F469 200D 1F9BD | woman in manual wheelchair | accessible |
| 👩‍🦽‍➡️ | 1F469 200D 1F9BD 200D 27A1 FE0F | woman in manual wheelchair facing right | accessible |
| 🏃 | 1F3C3 | person running | directions_run |
| 🏃‍♂️ | 1F3C3 200D 2642 FE0F | man running | directions_run |
| 🏃‍♀️ | 1F3C3 200D 2640 FE0F | woman running | directions_run |
| 🏃‍➡️ | 1F3C3 200D 27A1 FE0F | person running facing right | directions_run |
| 🏃‍♀️‍➡️ | 1F3C3 200D 2640 FE0F 200D 27A1 FE0F | woman running facing right | directions_run |
| 🏃‍♂️‍➡️ | 1F3C3 200D 2642 FE0F 200D 27A1 FE0F | man running facing right | directions_run |
| 💃 | 1F483 | woman dancing | nightlife |
| 🕺 | 1F57A | man dancing | nightlife |
| 🕴️ | 1F574 FE0F | person in suit levitating | person |
| 👯 | 1F46F | people with bunny ears | nightlife |
| 👯‍♂️ | 1F46F 200D 2642 FE0F | men with bunny ears | nightlife |
| 👯‍♀️ | 1F46F 200D 2640 FE0F | women with bunny ears | nightlife |
| 🧖 | 1F9D6 | person in steamy room | hot_tub |
| 🧖‍♂️ | 1F9D6 200D 2642 FE0F | man in steamy room | hot_tub |
| 🧖‍♀️ | 1F9D6 200D 2640 FE0F | woman in steamy room | hot_tub |
| 🧗 | 1F9D7 | person climbing | hiking |
| 🧗‍♂️ | 1F9D7 200D 2642 FE0F | man climbing | hiking |
| 🧗‍♀️ | 1F9D7 200D 2640 FE0F | woman climbing | hiking |
| 🤺 | 1F93A | person fencing | swords |
| 🏇 | 1F3C7 | horse racing | sports_score |
| ⛷️ | 26F7 FE0F | skier | downhill_skiing |
| 🏂 | 1F3C2 | snowboarder | snowboarding |
| 🏌️ | 1F3CC FE0F | person golfing | sports_golf |
| 🏌️‍♂️ | 1F3CC FE0F 200D 2642 FE0F | man golfing | sports_golf |
| 🏌️‍♀️ | 1F3CC FE0F 200D 2640 FE0F | woman golfing | sports_golf |
| 🏄 | 1F3C4 | person surfing | surfing |
| 🏄‍♂️ | 1F3C4 200D 2642 FE0F | man surfing | surfing |
| 🏄‍♀️ | 1F3C4 200D 2640 FE0F | woman surfing | surfing |
| 🚣 | 1F6A3 | person rowing boat | rowing |
| 🚣‍♂️ | 1F6A3 200D 2642 FE0F | man rowing boat | rowing |
| 🚣‍♀️ | 1F6A3 200D 2640 FE0F | woman rowing boat | rowing |
| 🏊 | 1F3CA | person swimming | pool |
| 🏊‍♂️ | 1F3CA 200D 2642 FE0F | man swimming | pool |
| 🏊‍♀️ | 1F3CA 200D 2640 FE0F | woman swimming | pool |
| ⛹️ | 26F9 FE0F | person bouncing ball | sports_basketball |
| ⛹️‍♂️ | 26F9 FE0F 200D 2642 FE0F | man bouncing ball | sports_basketball |
| ⛹️‍♀️ | 26F9 FE0F 200D 2640 FE0F | woman bouncing ball | sports_basketball |
| 🏋️ | 1F3CB FE0F | person lifting weights | fitness_center |
| 🏋️‍♂️ | 1F3CB FE0F 200D 2642 FE0F | man lifting weights | fitness_center |
| 🏋️‍♀️ | 1F3CB FE0F 200D 2640 FE0F | woman lifting weights | fitness_center |
| 🚴 | 1F6B4 | person biking | directions_bike |
| 🚴‍♂️ | 1F6B4 200D 2642 FE0F | man biking | directions_bike |
| 🚴‍♀️ | 1F6B4 200D 2640 FE0F | woman biking | directions_bike |
| 🚵 | 1F6B5 | person mountain biking | directions_bike |
| 🚵‍♂️ | 1F6B5 200D 2642 FE0F | man mountain biking | directions_bike |
| 🚵‍♀️ | 1F6B5 200D 2640 FE0F | woman mountain biking | directions_bike |
| 🤸 | 1F938 | person cartwheeling | sports_gymnastics |
| 🤸‍♂️ | 1F938 200D 2642 FE0F | man cartwheeling | sports_gymnastics |
| 🤸‍♀️ | 1F938 200D 2640 FE0F | woman cartwheeling | sports_gymnastics |
| 🤼 | 1F93C | people wrestling | sports_kabaddi |
| 🤼‍♂️ | 1F93C 200D 2642 FE0F | men wrestling | sports_kabaddi |
| 🤼‍♀️ | 1F93C 200D 2640 FE0F | women wrestling | sports_kabaddi |
| 🤽 | 1F93D | person playing water polo | pool |
| 🤽‍♂️ | 1F93D 200D 2642 FE0F | man playing water polo | pool |
| 🤽‍♀️ | 1F93D 200D 2640 FE0F | woman playing water polo | pool |
| 🤾 | 1F93E | person playing handball | sports_handball |
| 🤾‍♂️ | 1F93E 200D 2642 FE0F | man playing handball | sports_handball |
| 🤾‍♀️ | 1F93E 200D 2640 FE0F | woman playing handball | sports_handball |
| 🤹 | 1F939 | person juggling | sports_esports |
| 🤹‍♂️ | 1F939 200D 2642 FE0F | man juggling | sports_esports |
| 🤹‍♀️ | 1F939 200D 2640 FE0F | woman juggling | sports_esports |
| 🧘 | 1F9D8 | person in lotus position | self_improvement |
| 🧘‍♂️ | 1F9D8 200D 2642 FE0F | man in lotus position | self_improvement |
| 🧘‍♀️ | 1F9D8 200D 2640 FE0F | woman in lotus position | self_improvement |
| 🛀 | 1F6C0 | person taking bath | bathtub |
| 🛌 | 1F6CC | person in bed | bed |
| 🧑‍🤝‍🧑 | 1F9D1 200D 1F91D 200D 1F9D1 | people holding hands | group |
| 👭 | 1F46D | women holding hands | group |
| 👫 | 1F46B | woman and man holding hands | group |
| 👬 | 1F46C | men holding hands | group |
| 💏 | 1F48F | kiss | favorite |
| 👩‍❤️‍💋‍👨 | 1F469 200D 2764 FE0F 200D 1F48B 200D 1F468 | kiss: woman, man | favorite |
| 👨‍❤️‍💋‍👨 | 1F468 200D 2764 FE0F 200D 1F48B 200D 1F468 | kiss: man, man | favorite |
| 👩‍❤️‍💋‍👩 | 1F469 200D 2764 FE0F 200D 1F48B 200D 1F469 | kiss: woman, woman | favorite |
| 💑 | 1F491 | couple with heart | favorite |
| 👩‍❤️‍👨 | 1F469 200D 2764 FE0F 200D 1F468 | couple with heart: woman, man | favorite |
| 👨‍❤️‍👨 | 1F468 200D 2764 FE0F 200D 1F468 | couple with heart: man, man | favorite |
| 👩‍❤️‍👩 | 1F469 200D 2764 FE0F 200D 1F469 | couple with heart: woman, woman | favorite |
| 👨‍👩‍👦 | 1F468 200D 1F469 200D 1F466 | family: man, woman, boy | family_restroom |
| 👨‍👩‍👧 | 1F468 200D 1F469 200D 1F467 | family: man, woman, girl | family_restroom |
| 👨‍👩‍👧‍👦 | 1F468 200D 1F469 200D 1F467 200D 1F466 | family: man, woman, girl, boy | family_restroom |
| 👨‍👩‍👦‍👦 | 1F468 200D 1F469 200D 1F466 200D 1F466 | family: man, woman, boy, boy | family_restroom |
| 👨‍👩‍👧‍👧 | 1F468 200D 1F469 200D 1F467 200D 1F467 | family: man, woman, girl, girl | family_restroom |
| 👨‍👨‍👦 | 1F468 200D 1F468 200D 1F466 | family: man, man, boy | family_restroom |
| 👨‍👨‍👧 | 1F468 200D 1F468 200D 1F467 | family: man, man, girl | family_restroom |
| 👨‍👨‍👧‍👦 | 1F468 200D 1F468 200D 1F467 200D 1F466 | family: man, man, girl, boy | family_restroom |
| 👨‍👨‍👦‍👦 | 1F468 200D 1F468 200D 1F466 200D 1F466 | family: man, man, boy, boy | family_restroom |
| 👨‍👨‍👧‍👧 | 1F468 200D 1F468 200D 1F467 200D 1F467 | family: man, man, girl, girl | family_restroom |
| 👩‍👩‍👦 | 1F469 200D 1F469 200D 1F466 | family: woman, woman, boy | family_restroom |
| 👩‍👩‍👧 | 1F469 200D 1F469 200D 1F467 | family: woman, woman, girl | family_restroom |
| 👩‍👩‍👧‍👦 | 1F469 200D 1F469 200D 1F467 200D 1F466 | family: woman, woman, girl, boy | family_restroom |
| 👩‍👩‍👦‍👦 | 1F469 200D 1F469 200D 1F466 200D 1F466 | family: woman, woman, boy, boy | family_restroom |
| 👩‍👩‍👧‍👧 | 1F469 200D 1F469 200D 1F467 200D 1F467 | family: woman, woman, girl, girl | family_restroom |
| 👨‍👦 | 1F468 200D 1F466 | family: man, boy | family_restroom |
| 👨‍👦‍👦 | 1F468 200D 1F466 200D 1F466 | family: man, boy, boy | family_restroom |
| 👨‍👧 | 1F468 200D 1F467 | family: man, girl | family_restroom |
| 👨‍👧‍👦 | 1F468 200D 1F467 200D 1F466 | family: man, girl, boy | family_restroom |
| 👨‍👧‍👧 | 1F468 200D 1F467 200D 1F467 | family: man, girl, girl | family_restroom |
| 👩‍👦 | 1F469 200D 1F466 | family: woman, boy | family_restroom |
| 👩‍👦‍👦 | 1F469 200D 1F466 200D 1F466 | family: woman, boy, boy | family_restroom |
| 👩‍👧 | 1F469 200D 1F467 | family: woman, girl | family_restroom |
| 👩‍👧‍👦 | 1F469 200D 1F467 200D 1F466 | family: woman, girl, boy | family_restroom |
| 👩‍👧‍👧 | 1F469 200D 1F467 200D 1F467 | family: woman, girl, girl | family_restroom |
| 🗣️ | 1F5E3 FE0F | speaking head | record_voice_over |
| 👤 | 1F464 | bust in silhouette | person |
| 👥 | 1F465 | busts in silhouette | group |
| 🫂 | 1FAC2 | people hugging | diversity_1 |
| 👪 | 1F46A | family | family_restroom |
| 🧑‍🧑‍🧒 | 1F9D1 200D 1F9D1 200D 1F9D2 | family: adult, adult, child | family_restroom |
| 🧑‍🧑‍🧒‍🧒 | 1F9D1 200D 1F9D1 200D 1F9D2 200D 1F9D2 | family: adult, adult, child, child | family_restroom |
| 🧑‍🧒 | 1F9D1 200D 1F9D2 | family: adult, child | family_restroom |
| 🧑‍🧒‍🧒 | 1F9D1 200D 1F9D2 200D 1F9D2 | family: adult, child, child | family_restroom |
| 👣 | 1F463 | footprints | footprint |
| 🫆 | 1FAC6 | fingerprint | fingerprint |
| 🌍 | 1F30D | globe showing Europe-Africa | public |
| 🌎 | 1F30E | globe showing Americas | public |
| 🌏 | 1F30F | globe showing Asia-Australia | public |
| 🌐 | 1F310 | globe with meridians | language |
| 🗺️ | 1F5FA FE0F | world map | map |
| 🗾 | 1F5FE | map of Japan | map |
| 🧭 | 1F9ED | compass | explore |
| 🏔️ | 1F3D4 FE0F | snow-capped mountain | landscape |
| ⛰️ | 26F0 FE0F | mountain | landscape |
| 🌋 | 1F30B | volcano | volcano |
| 🗻 | 1F5FB | mount fuji | landscape |
| 🏕️ | 1F3D5 FE0F | camping | camping |
| 🏖️ | 1F3D6 FE0F | beach with umbrella | beach_access |
| 🏜️ | 1F3DC FE0F | desert | terrain |
| 🏝️ | 1F3DD FE0F | desert island | beach_access |
| 🏞️ | 1F3DE FE0F | national park | park |
| 🏟️ | 1F3DF FE0F | stadium | stadium |
| 🏛️ | 1F3DB FE0F | classical building | account_balance |
| 🏗️ | 1F3D7 FE0F | building construction | construction |
| 🧱 | 1F9F1 | brick | view_module |
| 🪨 | 1FAA8 | rock | terrain |
| 🪵 | 1FAB5 | wood | forest |
| 🛖 | 1F6D6 | hut | cottage |
| 🏘️ | 1F3D8 FE0F | houses | home_work |
| 🏚️ | 1F3DA FE0F | derelict house | house_siding |
| 🏠 | 1F3E0 | house | home |
| 🏡 | 1F3E1 | house with garden | cottage |
| 🏢 | 1F3E2 | office building | apartment |
| 🏣 | 1F3E3 | Japanese post office | local_post_office |
| 🏤 | 1F3E4 | post office | local_post_office |
| 🏥 | 1F3E5 | hospital | local_hospital |
| 🏦 | 1F3E6 | bank | account_balance |
| 🏨 | 1F3E8 | hotel | hotel |
| 🏩 | 1F3E9 | love hotel | bed |
| 🏪 | 1F3EA | convenience store | storefront |
| 🏫 | 1F3EB | school | school |
| 🏬 | 1F3EC | department store | store |
| 🏭 | 1F3ED | factory | factory |
| 🏯 | 1F3EF | Japanese castle | castle |
| 🏰 | 1F3F0 | castle | castle |
| 💒 | 1F492 | wedding | favorite |
| 🗼 | 1F5FC | Tokyo tower | cell_tower |
| 🗽 | 1F5FD | Statue of Liberty | attractions |
| ⛪ | 26EA | church | church |
| 🕌 | 1F54C | mosque | mosque |
| 🛕 | 1F6D5 | hindu temple | temple_hindu |
| 🕍 | 1F54D | synagogue | synagogue |
| ⛩️ | 26E9 FE0F | shinto shrine | temple_buddhist |
| 🕋 | 1F54B | kaaba | mosque |
| ⛲ | 26F2 | fountain | water_drop |
| ⛺ | 26FA | tent | camping |
| 🌁 | 1F301 | foggy | foggy |
| 🌃 | 1F303 | night with stars | nights_stay |
| 🏙️ | 1F3D9 FE0F | cityscape | location_city |
| 🌄 | 1F304 | sunrise over mountains | wb_twilight |
| 🌅 | 1F305 | sunrise | wb_twilight |
| 🌆 | 1F306 | cityscape at dusk | location_city |
| 🌇 | 1F307 | sunset | wb_twilight |
| 🌉 | 1F309 | bridge at night | flyover |
| ♨️ | 2668 FE0F | hot springs | hot_tub |
| 🎠 | 1F3A0 | carousel horse | attractions |
| 🛝 | 1F6DD | playground slide | attractions |
| 🎡 | 1F3A1 | ferris wheel | attractions |
| 🎢 | 1F3A2 | roller coaster | attractions |
| 💈 | 1F488 | barber pole | content_cut |
| 🎪 | 1F3AA | circus tent | festival |
| 🚂 | 1F682 | locomotive | train |
| 🚃 | 1F683 | railway car | directions_railway |
| 🚄 | 1F684 | high-speed train | train |
| 🚅 | 1F685 | bullet train | train |
| 🚆 | 1F686 | train | train |
| 🚇 | 1F687 | metro | subway |
| 🚈 | 1F688 | light rail | directions_transit |
| 🚉 | 1F689 | station | directions_transit |
| 🚊 | 1F68A | tram | tram |
| 🚝 | 1F69D | monorail | directions_transit |
| 🚞 | 1F69E | mountain railway | directions_railway |
| 🚋 | 1F68B | tram car | tram |
| 🚌 | 1F68C | bus | directions_bus |
| 🚍 | 1F68D | oncoming bus | directions_bus |
| 🚎 | 1F68E | trolleybus | directions_bus |
| 🚐 | 1F690 | minibus | airport_shuttle |
| 🚑 | 1F691 | ambulance | emergency |
| 🚒 | 1F692 | fire engine | fire_truck |
| 🚓 | 1F693 | police car | local_police |
| 🚔 | 1F694 | oncoming police car | local_police |
| 🚕 | 1F695 | taxi | local_taxi |
| 🚖 | 1F696 | oncoming taxi | local_taxi |
| 🚗 | 1F697 | automobile | directions_car |
| 🚘 | 1F698 | oncoming automobile | directions_car |
| 🚙 | 1F699 | sport utility vehicle | directions_car |
| 🛻 | 1F6FB | pickup truck | local_shipping |
| 🚚 | 1F69A | delivery truck | local_shipping |
| 🚛 | 1F69B | articulated lorry | local_shipping |
| 🚜 | 1F69C | tractor | agriculture |
| 🏎️ | 1F3CE FE0F | racing car | sports_score |
| 🏍️ | 1F3CD FE0F | motorcycle | two_wheeler |
| 🛵 | 1F6F5 | motor scooter | moped |
| 🦽 | 1F9BD | manual wheelchair | accessible |
| 🦼 | 1F9BC | motorized wheelchair | accessible |
| 🛺 | 1F6FA | auto rickshaw | electric_rickshaw |
| 🚲 | 1F6B2 | bicycle | pedal_bike |
| 🛴 | 1F6F4 | kick scooter | electric_scooter |
| 🛹 | 1F6F9 | skateboard | skateboarding |
| 🛼 | 1F6FC | roller skate | roller_skating |
| 🚏 | 1F68F | bus stop | directions_bus |
| 🛣️ | 1F6E3 FE0F | motorway | add_road |
| 🛤️ | 1F6E4 FE0F | railway track | directions_railway |
| 🛢️ | 1F6E2 FE0F | oil drum | oil_barrel |
| ⛽ | 26FD | fuel pump | local_gas_station |
| 🛞 | 1F6DE | wheel | tire_repair |
| 🚨 | 1F6A8 | police car light | emergency_heat |
| 🚥 | 1F6A5 | horizontal traffic light | traffic |
| 🚦 | 1F6A6 | vertical traffic light | traffic |
| 🛑 | 1F6D1 | stop sign | report |
| 🚧 | 1F6A7 | construction | construction |
| ⚓ | 2693 | anchor | anchor |
| 🛟 | 1F6DF | ring buoy | support |
| ⛵ | 26F5 | sailboat | sailing |
| 🛶 | 1F6F6 | canoe | kayaking |
| 🚤 | 1F6A4 | speedboat | directions_boat |
| 🛳️ | 1F6F3 FE0F | passenger ship | directions_boat |
| ⛴️ | 26F4 FE0F | ferry | directions_boat |
| 🛥️ | 1F6E5 FE0F | motor boat | directions_boat |
| 🚢 | 1F6A2 | ship | directions_boat |
| ✈️ | 2708 FE0F | airplane | flight |
| 🛩️ | 1F6E9 FE0F | small airplane | flight |
| 🛫 | 1F6EB | airplane departure | flight_takeoff |
| 🛬 | 1F6EC | airplane arrival | flight_land |
| 🪂 | 1FA82 | parachute | paragliding |
| 💺 | 1F4BA | seat | airline_seat_recline_normal |
| 🚁 | 1F681 | helicopter | helicopter |
| 🚟 | 1F69F | suspension railway | cable_car |
| 🚠 | 1F6A0 | mountain cableway | cable_car |
| 🚡 | 1F6A1 | aerial tramway | cable_car |
| 🛰️ | 1F6F0 FE0F | satellite | satellite_alt |
| 🚀 | 1F680 | rocket | rocket_launch |
| 🛸 | 1F6F8 | flying saucer | rocket |
| 🛎️ | 1F6CE FE0F | bellhop bell | room_service |
| 🧳 | 1F9F3 | luggage | luggage |
| ⌛ | 231B | hourglass done | hourglass_bottom |
| ⏳ | 23F3 | hourglass not done | hourglass_top |
| ⌚ | 231A | watch | watch |
| ⏰ | 23F0 | alarm clock | alarm |
| ⏱️ | 23F1 FE0F | stopwatch | timer |
| ⏲️ | 23F2 FE0F | timer clock | av_timer |
| 🕰️ | 1F570 FE0F | mantelpiece clock | schedule |
| 🕛 | 1F55B | twelve o’clock | schedule |
| 🕧 | 1F567 | twelve-thirty | schedule |
| 🕐 | 1F550 | one o’clock | schedule |
| 🕜 | 1F55C | one-thirty | schedule |
| 🕑 | 1F551 | two o’clock | schedule |
| 🕝 | 1F55D | two-thirty | schedule |
| 🕒 | 1F552 | three o’clock | schedule |
| 🕞 | 1F55E | three-thirty | schedule |
| 🕓 | 1F553 | four o’clock | schedule |
| 🕟 | 1F55F | four-thirty | schedule |
| 🕔 | 1F554 | five o’clock | schedule |
| 🕠 | 1F560 | five-thirty | schedule |
| 🕕 | 1F555 | six o’clock | schedule |
| 🕡 | 1F561 | six-thirty | schedule |
| 🕖 | 1F556 | seven o’clock | schedule |
| 🕢 | 1F562 | seven-thirty | schedule |
| 🕗 | 1F557 | eight o’clock | schedule |
| 🕣 | 1F563 | eight-thirty | schedule |
| 🕘 | 1F558 | nine o’clock | schedule |
| 🕤 | 1F564 | nine-thirty | schedule |
| 🕙 | 1F559 | ten o’clock | schedule |
| 🕥 | 1F565 | ten-thirty | schedule |
| 🕚 | 1F55A | eleven o’clock | schedule |
| 🕦 | 1F566 | eleven-thirty | schedule |
| 🌑 | 1F311 | new moon | brightness_3 |
| 🌒 | 1F312 | waxing crescent moon | bedtime |
| 🌓 | 1F313 | first quarter moon | contrast |
| 🌔 | 1F314 | waxing gibbous moon | brightness_2 |
| 🌕 | 1F315 | full moon | circle:filled |
| 🌖 | 1F316 | waning gibbous moon | brightness_2 |
| 🌗 | 1F317 | last quarter moon | contrast |
| 🌘 | 1F318 | waning crescent moon | bedtime |
| 🌙 | 1F319 | crescent moon | bedtime |
| 🌚 | 1F31A | new moon face | dark_mode |
| 🌛 | 1F31B | first quarter moon face | dark_mode |
| 🌜 | 1F31C | last quarter moon face | dark_mode |
| 🌡️ | 1F321 FE0F | thermometer | thermostat |
| ☀️ | 2600 FE0F | sun | sunny |
| 🌝 | 1F31D | full moon face | circle:filled |
| 🌞 | 1F31E | sun with face | light_mode |
| 🪐 | 1FA90 | ringed planet | planet |
| ⭐ | 2B50 | star | star:filled |
| 🌟 | 1F31F | glowing star | auto_awesome |
| 🌠 | 1F320 | shooting star | auto_awesome |
| 🌌 | 1F30C | milky way | stars |
| ☁️ | 2601 FE0F | cloud | cloud |
| ⛅ | 26C5 | sun behind cloud | partly_cloudy_day |
| ⛈️ | 26C8 FE0F | cloud with lightning and rain | thunderstorm |
| 🌤️ | 1F324 FE0F | sun behind small cloud | partly_cloudy_day |
| 🌥️ | 1F325 FE0F | sun behind large cloud | partly_cloudy_day |
| 🌦️ | 1F326 FE0F | sun behind rain cloud | partly_cloudy_day |
| 🌧️ | 1F327 FE0F | cloud with rain | rainy |
| 🌨️ | 1F328 FE0F | cloud with snow | cloudy_snowing |
| 🌩️ | 1F329 FE0F | cloud with lightning | thunderstorm |
| 🌪️ | 1F32A FE0F | tornado | tornado |
| 🌫️ | 1F32B FE0F | fog | foggy |
| 🌬️ | 1F32C FE0F | wind face | air |
| 🌀 | 1F300 | cyclone | cyclone |
| 🌈 | 1F308 | rainbow | wb_twilight |
| 🌂 | 1F302 | closed umbrella | umbrella |
| ☂️ | 2602 FE0F | umbrella | umbrella |
| ☔ | 2614 | umbrella with rain drops | umbrella |
| ⛱️ | 26F1 FE0F | umbrella on ground | beach_access |
| ⚡ | 26A1 | high voltage | bolt |
| ❄️ | 2744 FE0F | snowflake | ac_unit |
| ☃️ | 2603 FE0F | snowman | weather_snowy |
| ⛄ | 26C4 | snowman without snow | weather_snowy |
| ☄️ | 2604 FE0F | comet | flare |
| 🔥 | 1F525 | fire | local_fire_department |
| 💧 | 1F4A7 | droplet | water_drop |
| 🌊 | 1F30A | water wave | waves |
| 🎃 | 1F383 | jack-o-lantern | nightlight |
| 🎄 | 1F384 | Christmas tree | park |
| 🎆 | 1F386 | fireworks | celebration |
| 🎇 | 1F387 | sparkler | celebration |
| 🧨 | 1F9E8 | firecracker | celebration |
| ✨ | 2728 | sparkles | auto_awesome |
| 🎈 | 1F388 | balloon | celebration |
| 🎉 | 1F389 | party popper | celebration |
| 🎊 | 1F38A | confetti ball | celebration |
| 🎋 | 1F38B | tanabata tree | park |
| 🎍 | 1F38D | pine decoration | park |
| 🎎 | 1F38E | Japanese dolls | toys |
| 🎏 | 1F38F | carp streamer | flag |
| 🎐 | 1F390 | wind chime | notifications |
| 🎑 | 1F391 | moon viewing ceremony | bedtime |
| 🧧 | 1F9E7 | red envelope | mail |
| 🎀 | 1F380 | ribbon | redeem |
| 🎁 | 1F381 | wrapped gift | featured_seasonal_and_gifts |
| 🎗️ | 1F397 FE0F | reminder ribbon | workspace_premium |
| 🎟️ | 1F39F FE0F | admission tickets | confirmation_number |
| 🎫 | 1F3AB | ticket | local_activity |
| 🎖️ | 1F396 FE0F | military medal | military_tech |
| 🏆 | 1F3C6 | trophy | emoji_events |
| 🏅 | 1F3C5 | sports medal | military_tech |
| 🥇 | 1F947 | 1st place medal | workspace_premium |
| 🥈 | 1F948 | 2nd place medal | workspace_premium |
| 🥉 | 1F949 | 3rd place medal | workspace_premium |
| ⚽ | 26BD | soccer ball | sports_soccer |
| ⚾ | 26BE | baseball | sports_baseball |
| 🥎 | 1F94E | softball | sports_baseball |
| 🏀 | 1F3C0 | basketball | sports_basketball |
| 🏐 | 1F3D0 | volleyball | sports_volleyball |
| 🏈 | 1F3C8 | american football | sports_football |
| 🏉 | 1F3C9 | rugby football | sports_rugby |
| 🎾 | 1F3BE | tennis | sports_tennis |
| 🥏 | 1F94F | flying disc | sports |
| 🎳 | 1F3B3 | bowling | sports |
| 🏏 | 1F3CF | cricket game | sports_cricket |
| 🏑 | 1F3D1 | field hockey | sports_hockey |
| 🏒 | 1F3D2 | ice hockey | sports_hockey |
| 🥍 | 1F94D | lacrosse | sports |
| 🏓 | 1F3D3 | ping pong | sports_tennis |
| 🏸 | 1F3F8 | badminton | sports_tennis |
| 🥊 | 1F94A | boxing glove | sports_mma |
| 🥋 | 1F94B | martial arts uniform | sports_martial_arts |
| 🥅 | 1F945 | goal net | sports_soccer |
| ⛳ | 26F3 | flag in hole | sports_golf |
| ⛸️ | 26F8 FE0F | ice skate | ice_skating |
| 🎣 | 1F3A3 | fishing pole | phishing |
| 🤿 | 1F93F | diving mask | scuba_diving |
| 🎽 | 1F3BD | running shirt | checkroom |
| 🎿 | 1F3BF | skis | downhill_skiing |
| 🛷 | 1F6F7 | sled | sledding |
| 🥌 | 1F94C | curling stone | sports |
| 🎯 | 1F3AF | bullseye | target |
| 🪀 | 1FA80 | yo-yo | toys |
| 🪁 | 1FA81 | kite | toys |
| 🔫 | 1F52B | water pistol | toys |
| 🎱 | 1F3B1 | pool 8 ball | sports |
| 🔮 | 1F52E | crystal ball | auto_fix_high |
| 🪄 | 1FA84 | magic wand | auto_fix_high |
| 🎮 | 1F3AE | video game | sports_esports |
| 🕹️ | 1F579 FE0F | joystick | joystick |
| 🎰 | 1F3B0 | slot machine | casino |
| 🎲 | 1F3B2 | game die | casino |
| 🧩 | 1F9E9 | puzzle piece | extension |
| 🧸 | 1F9F8 | teddy bear | smart_toy |
| 🪅 | 1FA85 | piñata | celebration |
| 🪩 | 1FAA9 | mirror ball | nightlife |
| 🪆 | 1FA86 | nesting dolls | toys |
| ♠️ | 2660 FE0F | spade suit | playing_cards |
| ♥️ | 2665 FE0F | heart suit | favorite:filled |
| ♦️ | 2666 FE0F | diamond suit | diamond:filled |
| ♣️ | 2663 FE0F | club suit | playing_cards |
| ♟️ | 265F FE0F | chess pawn | chess |
| 🃏 | 1F0CF | joker | playing_cards |
| 🀄 | 1F004 | mahjong red dragon | playing_cards |
| 🎴 | 1F3B4 | flower playing cards | playing_cards |
| 🎭 | 1F3AD | performing arts | theater_comedy |
| 🖼️ | 1F5BC FE0F | framed picture | image |
| 🎨 | 1F3A8 | artist palette | palette |
| 🧵 | 1F9F5 | thread | line_curve |
| 🪡 | 1FAA1 | sewing needle | line_curve |
| 🧶 | 1F9F6 | yarn | line_curve |
| 🪢 | 1FAA2 | knot | line_curve |
| 🍇 | 1F347 | grapes | nutrition |
| 🍈 | 1F348 | melon | nutrition |
| 🍉 | 1F349 | watermelon | nutrition |
| 🍊 | 1F34A | tangerine | nutrition |
| 🍋 | 1F34B | lemon | nutrition |
| 🍋‍🟩 | 1F34B 200D 1F7E9 | lime | nutrition |
| 🍌 | 1F34C | banana | nutrition |
| 🍍 | 1F34D | pineapple | nutrition |
| 🥭 | 1F96D | mango | nutrition |
| 🍎 | 1F34E | red apple | nutrition |
| 🍏 | 1F34F | green apple | nutrition |
| 🍐 | 1F350 | pear | nutrition |
| 🍑 | 1F351 | peach | nutrition |
| 🍒 | 1F352 | cherries | nutrition |
| 🍓 | 1F353 | strawberry | nutrition |
| 🫐 | 1FAD0 | blueberries | nutrition |
| 🥝 | 1F95D | kiwi fruit | nutrition |
| 🍅 | 1F345 | tomato | nutrition |
| 🫒 | 1FAD2 | olive | eco |
| 🥥 | 1F965 | coconut | nutrition |
| 🥑 | 1F951 | avocado | avocado_bean |
| 🍆 | 1F346 | eggplant | eco |
| 🥔 | 1F954 | potato | eco |
| 🥕 | 1F955 | carrot | nutrition |
| 🌽 | 1F33D | ear of corn | grass |
| 🌶️ | 1F336 FE0F | hot pepper | local_fire_department |
| 🫑 | 1FAD1 | bell pepper | eco |
| 🥒 | 1F952 | cucumber | eco |
| 🥬 | 1F96C | leafy green | eco |
| 🥦 | 1F966 | broccoli | eco |
| 🧄 | 1F9C4 | garlic | eco |
| 🧅 | 1F9C5 | onion | eco |
| 🥜 | 1F95C | peanuts | eco |
| 🫘 | 1FAD8 | beans | avocado_bean |
| 🌰 | 1F330 | chestnut | eco |
| 🫚 | 1FADA | ginger root | eco |
| 🫛 | 1FADB | pea pod | eco |
| 🍄‍🟫 | 1F344 200D 1F7EB | brown mushroom | eco |
| 🫜 | 1FADC | root vegetable | eco |
| 🍞 | 1F35E | bread | bakery_dining |
| 🥐 | 1F950 | croissant | bakery_dining |
| 🥖 | 1F956 | baguette bread | bakery_dining |
| 🫓 | 1FAD3 | flatbread | bakery_dining |
| 🥨 | 1F968 | pretzel | bakery_dining |
| 🥯 | 1F96F | bagel | bakery_dining |
| 🥞 | 1F95E | pancakes | breakfast_dining |
| 🧇 | 1F9C7 | waffle | breakfast_dining |
| 🧀 | 1F9C0 | cheese wedge | lunch_dining |
| 🍖 | 1F356 | meat on bone | kebab_dining |
| 🍗 | 1F357 | poultry leg | kebab_dining |
| 🥩 | 1F969 | cut of meat | kebab_dining |
| 🥓 | 1F953 | bacon | breakfast_dining |
| 🍔 | 1F354 | hamburger | lunch_dining |
| 🍟 | 1F35F | french fries | fastfood |
| 🍕 | 1F355 | pizza | local_pizza |
| 🌭 | 1F32D | hot dog | fastfood |
| 🥪 | 1F96A | sandwich | lunch_dining |
| 🌮 | 1F32E | taco | lunch_dining |
| 🌯 | 1F32F | burrito | lunch_dining |
| 🫔 | 1FAD4 | tamale | lunch_dining |
| 🥙 | 1F959 | stuffed flatbread | lunch_dining |
| 🧆 | 1F9C6 | falafel | tapas |
| 🥚 | 1F95A | egg | egg |
| 🍳 | 1F373 | cooking | skillet |
| 🥘 | 1F958 | shallow pan of food | skillet |
| 🍲 | 1F372 | pot of food | stockpot |
| 🫕 | 1FAD5 | fondue | stockpot |
| 🥣 | 1F963 | bowl with spoon | soup_kitchen |
| 🥗 | 1F957 | green salad | nutrition |
| 🍿 | 1F37F | popcorn | movie |
| 🧈 | 1F9C8 | butter | bakery_dining |
| 🧂 | 1F9C2 | salt | grain |
| 🥫 | 1F96B | canned food | food_bank |
| 🍱 | 1F371 | bento box | bento |
| 🍘 | 1F358 | rice cracker | rice_bowl |
| 🍙 | 1F359 | rice ball | rice_bowl |
| 🍚 | 1F35A | cooked rice | rice_bowl |
| 🍛 | 1F35B | curry rice | japanese_curry |
| 🍜 | 1F35C | steaming bowl | ramen_dining |
| 🍝 | 1F35D | spaghetti | dinner_dining |
| 🍠 | 1F360 | roasted sweet potato | eco |
| 🍢 | 1F362 | oden | yakitori |
| 🍣 | 1F363 | sushi | set_meal |
| 🍤 | 1F364 | fried shrimp | set_meal |
| 🍥 | 1F365 | fish cake with swirl | set_meal |
| 🥮 | 1F96E | moon cake | cookie |
| 🍡 | 1F361 | dango | hanami_dango |
| 🥟 | 1F95F | dumpling | dinner_dining |
| 🥠 | 1F960 | fortune cookie | cookie |
| 🥡 | 1F961 | takeout box | takeout_dining |
| 🍦 | 1F366 | soft ice cream | icecream |
| 🍧 | 1F367 | shaved ice | shaved_ice |
| 🍨 | 1F368 | ice cream | icecream |
| 🍩 | 1F369 | doughnut | donut_small |
| 🍪 | 1F36A | cookie | cookie |
| 🎂 | 1F382 | birthday cake | cake |
| 🍰 | 1F370 | shortcake | cake |
| 🧁 | 1F9C1 | cupcake | cake |
| 🥧 | 1F967 | pie | cake |
| 🍫 | 1F36B | chocolate bar | cookie |
| 🍬 | 1F36C | candy | cookie |
| 🍭 | 1F36D | lollipop | cookie |
| 🍮 | 1F36E | custard | cake |
| 🍯 | 1F36F | honey pot | kitchen |
| 🍼 | 1F37C | baby bottle | water_bottle |
| 🥛 | 1F95B | glass of milk | glass_cup |
| ☕ | 2615 | hot beverage | coffee |
| 🫖 | 1FAD6 | teapot | emoji_food_beverage |
| 🍵 | 1F375 | teacup without handle | emoji_food_beverage |
| 🍶 | 1F376 | sake | liquor |
| 🍾 | 1F37E | bottle with popping cork | liquor |
| 🍷 | 1F377 | wine glass | wine_bar |
| 🍸 | 1F378 | cocktail glass | local_bar |
| 🍹 | 1F379 | tropical drink | local_bar |
| 🍺 | 1F37A | beer mug | sports_bar |
| 🍻 | 1F37B | clinking beer mugs | sports_bar |
| 🥂 | 1F942 | clinking glasses | celebration |
| 🥃 | 1F943 | tumbler glass | local_bar |
| 🫗 | 1FAD7 | pouring liquid | water_drop |
| 🥤 | 1F964 | cup with straw | local_drink |
| 🧋 | 1F9CB | bubble tea | local_drink |
| 🧃 | 1F9C3 | beverage box | local_drink |
| 🧉 | 1F9C9 | mate | emoji_food_beverage |
| 🧊 | 1F9CA | ice | ac_unit |
| 🥢 | 1F962 | chopsticks | ramen_dining |
| 🍽️ | 1F37D FE0F | fork and knife with plate | restaurant |
| 🍴 | 1F374 | fork and knife | restaurant |
| 🥄 | 1F944 | spoon | flatware |
| 🔪 | 1F52A | kitchen knife | restaurant |
| 🫙 | 1FAD9 | jar | kitchen |
| 🏺 | 1F3FA | amphora | water_full |
| 👓 | 1F453 | glasses | eyeglasses |
| 🕶️ | 1F576 FE0F | sunglasses | eyeglasses |
| 🥽 | 1F97D | goggles | eyeglasses |
| 🥼 | 1F97C | lab coat | science |
| 🦺 | 1F9BA | safety vest | engineering |
| 👔 | 1F454 | necktie | work |
| 👕 | 1F455 | t-shirt | checkroom |
| 👖 | 1F456 | jeans | checkroom |
| 🧣 | 1F9E3 | scarf | checkroom |
| 🧤 | 1F9E4 | gloves | back_hand |
| 🧥 | 1F9E5 | coat | checkroom |
| 🧦 | 1F9E6 | socks | checkroom |
| 👗 | 1F457 | dress | checkroom |
| 👘 | 1F458 | kimono | checkroom |
| 🥻 | 1F97B | sari | checkroom |
| 🩱 | 1FA71 | one-piece swimsuit | checkroom |
| 🩲 | 1FA72 | briefs | checkroom |
| 🩳 | 1FA73 | shorts | checkroom |
| 👙 | 1F459 | bikini | checkroom |
| 👚 | 1F45A | woman’s clothes | checkroom |
| 🪭 | 1FAAD | folding hand fan | air |
| 👛 | 1F45B | purse | account_balance_wallet |
| 👜 | 1F45C | handbag | shopping_bag |
| 👝 | 1F45D | clutch bag | account_balance_wallet |
| 🛍️ | 1F6CD FE0F | shopping bags | shopping_bag |
| 🎒 | 1F392 | backpack | backpack |
| 🩴 | 1FA74 | thong sandal | footprint |
| 👞 | 1F45E | man’s shoe | steps |
| 👟 | 1F45F | running shoe | sprint |
| 🥾 | 1F97E | hiking boot | hiking |
| 🥿 | 1F97F | flat shoe | steps |
| 👠 | 1F460 | high-heeled shoe | steps |
| 👡 | 1F461 | woman’s sandal | footprint |
| 🩰 | 1FA70 | ballet shoes | steps |
| 👢 | 1F462 | woman’s boot | steps |
| 🪮 | 1FAAE | hair pick | content_cut |
| 👑 | 1F451 | crown | workspace_premium |
| 👒 | 1F452 | woman’s hat | checkroom |
| 🎩 | 1F3A9 | top hat | school |
| 🎓 | 1F393 | graduation cap | school |
| 🧢 | 1F9E2 | billed cap | checkroom |
| 🪖 | 1FA96 | military helmet | military_tech |
| ⛑️ | 26D1 FE0F | rescue worker’s helmet | engineering |
| 📿 | 1F4FF | prayer beads | diamond |
| 💄 | 1F484 | lipstick | health_and_beauty |
| 💍 | 1F48D | ring | diamond |
| 💎 | 1F48E | gem stone | diamond |
| 🔇 | 1F507 | muted speaker | volume_off |
| 🔈 | 1F508 | speaker low volume | volume_down |
| 🔉 | 1F509 | speaker medium volume | volume_down |
| 🔊 | 1F50A | speaker high volume | volume_up |
| 📢 | 1F4E2 | loudspeaker | campaign |
| 📣 | 1F4E3 | megaphone | campaign |
| 📯 | 1F4EF | postal horn | campaign |
| 🔔 | 1F514 | bell | notifications |
| 🔕 | 1F515 | bell with slash | notifications_off |
| 🎼 | 1F3BC | musical score | library_music |
| 🎵 | 1F3B5 | musical note | music_note |
| 🎶 | 1F3B6 | musical notes | library_music |
| 🎙️ | 1F399 FE0F | studio microphone | mic |
| 🎚️ | 1F39A FE0F | level slider | tune |
| 🎛️ | 1F39B FE0F | control knobs | tune |
| 🎤 | 1F3A4 | microphone | mic |
| 🎧 | 1F3A7 | headphone | headphones |
| 📻 | 1F4FB | radio | radio |
| 🎷 | 1F3B7 | saxophone | music_note |
| 🪗 | 1FA97 | accordion | music_note |
| 🎸 | 1F3B8 | guitar | music_note |
| 🎹 | 1F3B9 | musical keyboard | piano |
| 🎺 | 1F3BA | trumpet | music_note |
| 🎻 | 1F3BB | violin | music_note |
| 🪕 | 1FA95 | banjo | music_note |
| 🥁 | 1F941 | drum | music_note |
| 🪘 | 1FA98 | long drum | music_note |
| 🪇 | 1FA87 | maracas | music_note |
| 🪈 | 1FA88 | flute | music_note |
| 🪉 | 1FA89 | harp | music_note |
| 📱 | 1F4F1 | mobile phone | smartphone |
| 📲 | 1F4F2 | mobile phone with arrow | smartphone |
| ☎️ | 260E FE0F | telephone | call |
| 📞 | 1F4DE | telephone receiver | call |
| 📟 | 1F4DF | pager | smartphone |
| 📠 | 1F4E0 | fax machine | fax |
| 🔋 | 1F50B | battery | battery_full |
| 🪫 | 1FAAB | low battery | battery_alert |
| 🔌 | 1F50C | electric plug | power |
| 💻 | 1F4BB | laptop | laptop |
| 🖥️ | 1F5A5 FE0F | desktop computer | desktop_windows |
| 🖨️ | 1F5A8 FE0F | printer | print |
| ⌨️ | 2328 FE0F | keyboard | keyboard |
| 🖱️ | 1F5B1 FE0F | computer mouse | mouse |
| 🖲️ | 1F5B2 FE0F | trackball | mouse |
| 💽 | 1F4BD | computer disk | save |
| 💾 | 1F4BE | floppy disk | save |
| 💿 | 1F4BF | optical disk | album |
| 📀 | 1F4C0 | dvd | album |
| 🧮 | 1F9EE | abacus | calculate |
| 🎥 | 1F3A5 | movie camera | videocam |
| 🎞️ | 1F39E FE0F | film frames | movie |
| 📽️ | 1F4FD FE0F | film projector | movie |
| 🎬 | 1F3AC | clapper board | movie |
| 📺 | 1F4FA | television | tv |
| 📷 | 1F4F7 | camera | photo_camera |
| 📸 | 1F4F8 | camera with flash | photo_camera |
| 📹 | 1F4F9 | video camera | videocam |
| 📼 | 1F4FC | videocassette | video_library |
| 🔍 | 1F50D | magnifying glass tilted left | search |
| 🔎 | 1F50E | magnifying glass tilted right | search |
| 🕯️ | 1F56F FE0F | candle | candle |
| 💡 | 1F4A1 | light bulb | lightbulb |
| 🔦 | 1F526 | flashlight | flashlight_on |
| 🏮 | 1F3EE | red paper lantern | lightbulb |
| 🪔 | 1FA94 | diya lamp | candle |
| 📔 | 1F4D4 | notebook with decorative cover | book |
| 📕 | 1F4D5 | closed book | book |
| 📖 | 1F4D6 | open book | menu_book |
| 📗 | 1F4D7 | green book | book |
| 📘 | 1F4D8 | blue book | book |
| 📙 | 1F4D9 | orange book | book |
| 📚 | 1F4DA | books | auto_stories |
| 📓 | 1F4D3 | notebook | book |
| 📒 | 1F4D2 | ledger | book |
| 📃 | 1F4C3 | page with curl | description |
| 📜 | 1F4DC | scroll | description |
| 📄 | 1F4C4 | page facing up | description |
| 📰 | 1F4F0 | newspaper | newspaper |
| 🗞️ | 1F5DE FE0F | rolled-up newspaper | newspaper |
| 📑 | 1F4D1 | bookmark tabs | bookmarks |
| 🔖 | 1F516 | bookmark | bookmark |
| 🏷️ | 1F3F7 FE0F | label | sell |
| 💰 | 1F4B0 | money bag | money_bag |
| 🪙 | 1FA99 | coin | paid |
| 💴 | 1F4B4 | yen banknote | payments |
| 💵 | 1F4B5 | dollar banknote | payments |
| 💶 | 1F4B6 | euro banknote | payments |
| 💷 | 1F4B7 | pound banknote | payments |
| 💸 | 1F4B8 | money with wings | currency_exchange |
| 💳 | 1F4B3 | credit card | credit_card |
| 🧾 | 1F9FE | receipt | receipt_long |
| 💹 | 1F4B9 | chart increasing with yen | trending_up |
| ✉️ | 2709 FE0F | envelope | mail |
| 📧 | 1F4E7 | e-mail | email |
| 📨 | 1F4E8 | incoming envelope | move_to_inbox |
| 📩 | 1F4E9 | envelope with arrow | forward_to_inbox |
| 📤 | 1F4E4 | outbox tray | outbox |
| 📥 | 1F4E5 | inbox tray | move_to_inbox |
| 📦 | 1F4E6 | package | package_2 |
| 📫 | 1F4EB | closed mailbox with raised flag | markunread_mailbox |
| 📪 | 1F4EA | closed mailbox with lowered flag | markunread_mailbox |
| 📬 | 1F4EC | open mailbox with raised flag | markunread_mailbox |
| 📭 | 1F4ED | open mailbox with lowered flag | markunread_mailbox |
| 📮 | 1F4EE | postbox | markunread_mailbox |
| 🗳️ | 1F5F3 FE0F | ballot box with ballot | how_to_vote |
| ✏️ | 270F FE0F | pencil | edit |
| ✒️ | 2712 FE0F | black nib | edit |
| 🖋️ | 1F58B FE0F | fountain pen | edit |
| 🖊️ | 1F58A FE0F | pen | edit |
| 🖌️ | 1F58C FE0F | paintbrush | brush |
| 🖍️ | 1F58D FE0F | crayon | draw |
| 📝 | 1F4DD | memo | edit_note |
| 💼 | 1F4BC | briefcase | work |
| 📁 | 1F4C1 | file folder | folder |
| 📂 | 1F4C2 | open file folder | folder_open |
| 🗂️ | 1F5C2 FE0F | card index dividers | topic |
| 📅 | 1F4C5 | calendar | calendar_month |
| 📆 | 1F4C6 | tear-off calendar | event |
| 🗒️ | 1F5D2 FE0F | spiral notepad | note |
| 🗓️ | 1F5D3 FE0F | spiral calendar | calendar_month |
| 📇 | 1F4C7 | card index | contacts |
| 📈 | 1F4C8 | chart increasing | trending_up |
| 📉 | 1F4C9 | chart decreasing | trending_down |
| 📊 | 1F4CA | bar chart | bar_chart |
| 📋 | 1F4CB | clipboard | assignment |
| 📌 | 1F4CC | pushpin | push_pin |
| 📍 | 1F4CD | round pushpin | location_on |
| 📎 | 1F4CE | paperclip | attach_file |
| 🖇️ | 1F587 FE0F | linked paperclips | attach_file |
| 📏 | 1F4CF | straight ruler | straighten |
| 📐 | 1F4D0 | triangular ruler | architecture |
| ✂️ | 2702 FE0F | scissors | content_cut |
| 🗃️ | 1F5C3 FE0F | card file box | inventory |
| 🗄️ | 1F5C4 FE0F | file cabinet | archive |
| 🗑️ | 1F5D1 FE0F | wastebasket | delete |
| 🔒 | 1F512 | locked | lock |
| 🔓 | 1F513 | unlocked | lock_open |
| 🔏 | 1F50F | locked with pen | lock |
| 🔐 | 1F510 | locked with key | lock |
| 🔑 | 1F511 | key | key |
| 🗝️ | 1F5DD FE0F | old key | key |
| 🔨 | 1F528 | hammer | construction |
| 🪓 | 1FA93 | axe | construction |
| ⛏️ | 26CF FE0F | pick | construction |
| ⚒️ | 2692 FE0F | hammer and pick | construction |
| 🛠️ | 1F6E0 FE0F | hammer and wrench | handyman |
| 🗡️ | 1F5E1 FE0F | dagger | content_cut |
| ⚔️ | 2694 FE0F | crossed swords | sports_martial_arts |
| 💣 | 1F4A3 | bomb | warning |
| 🪃 | 1FA83 | boomerang | replay |
| 🏹 | 1F3F9 | bow and arrow | target |
| 🛡️ | 1F6E1 FE0F | shield | shield |
| 🪚 | 1FA9A | carpentry saw | carpenter |
| 🔧 | 1F527 | wrench | build |
| 🪛 | 1FA9B | screwdriver | build |
| 🔩 | 1F529 | nut and bolt | settings |
| ⚙️ | 2699 FE0F | gear | settings |
| 🗜️ | 1F5DC FE0F | clamp | build |
| ⚖️ | 2696 FE0F | balance scale | balance |
| 🦯 | 1F9AF | white cane | blind |
| 🔗 | 1F517 | link | link |
| ⛓️‍💥 | 26D3 FE0F 200D 1F4A5 | broken chain | link_off |
| ⛓️ | 26D3 FE0F | chains | link |
| 🪝 | 1FA9D | hook | link |
| 🧰 | 1F9F0 | toolbox | home_repair_service |
| 🧲 | 1F9F2 | magnet | sensors |
| 🪜 | 1FA9C | ladder | stairs |
| 🪏 | 1FA8F | shovel | construction |
| ⚗️ | 2697 FE0F | alembic | science |
| 🧪 | 1F9EA | test tube | science |
| 🧫 | 1F9EB | petri dish | biotech |
| 🧬 | 1F9EC | dna | genetics |
| 🔬 | 1F52C | microscope | biotech |
| 🔭 | 1F52D | telescope | travel_explore |
| 📡 | 1F4E1 | satellite antenna | satellite_alt |
| 💉 | 1F489 | syringe | vaccines |
| 🩸 | 1FA78 | drop of blood | bloodtype |
| 💊 | 1F48A | pill | medication |
| 🩹 | 1FA79 | adhesive bandage | healing |
| 🩼 | 1FA7C | crutch | accessible |
| 🩺 | 1FA7A | stethoscope | stethoscope |
| 🩻 | 1FA7B | x-ray | radiology |
| 🚪 | 1F6AA | door | door_front |
| 🛗 | 1F6D7 | elevator | elevator |
| 🪞 | 1FA9E | mirror | dresser |
| 🪟 | 1FA9F | window | window |
| 🛏️ | 1F6CF FE0F | bed | bed |
| 🛋️ | 1F6CB FE0F | couch and lamp | weekend |
| 🪑 | 1FA91 | chair | chair |
| 🚽 | 1F6BD | toilet | wc |
| 🪠 | 1FAA0 | plunger | plumbing |
| 🚿 | 1F6BF | shower | shower |
| 🛁 | 1F6C1 | bathtub | bathtub |
| 🪤 | 1FAA4 | mouse trap | pest_control |
| 🪒 | 1FA92 | razor | content_cut |
| 🧴 | 1F9F4 | lotion bottle | sanitizer |
| 🧷 | 1F9F7 | safety pin | push_pin |
| 🧹 | 1F9F9 | broom | cleaning_services |
| 🧺 | 1F9FA | basket | shopping_basket |
| 🧻 | 1F9FB | roll of paper | wc |
| 🪣 | 1FAA3 | bucket | cleaning_services |
| 🧼 | 1F9FC | soap | soap |
| 🫧 | 1FAE7 | bubbles | bubbles |
| 🪥 | 1FAA5 | toothbrush | dentistry |
| 🧽 | 1F9FD | sponge | cleaning_services |
| 🧯 | 1F9EF | fire extinguisher | fire_extinguisher |
| 🛒 | 1F6D2 | shopping cart | shopping_cart |
| 🚬 | 1F6AC | cigarette | smoking_rooms |
| ⚰️ | 26B0 FE0F | coffin | sentiment_very_dissatisfied |
| 🪦 | 1FAA6 | headstone | deceased |
| ⚱️ | 26B1 FE0F | funeral urn | deceased |
| 🧿 | 1F9FF | nazar amulet | shield |
| 🪬 | 1FAAC | hamsa | shield |
| 🗿 | 1F5FF | moai | landscape |
| 🪧 | 1FAA7 | placard | table_sign |
| 🪪 | 1FAAA | identification card | badge |
| 🏧 | 1F3E7 | ATM sign | local_atm |
| 🚮 | 1F6AE | litter in bin sign | delete |
| 🚰 | 1F6B0 | potable water | water_drop |
| ♿ | 267F | wheelchair symbol | accessible |
| 🚹 | 1F6B9 | men’s room | man |
| 🚺 | 1F6BA | women’s room | woman |
| 🚻 | 1F6BB | restroom | wc |
| 🚼 | 1F6BC | baby symbol | child_care |
| 🚾 | 1F6BE | water closet | wc |
| 🛂 | 1F6C2 | passport control | passport |
| 🛃 | 1F6C3 | customs | local_police |
| 🛄 | 1F6C4 | baggage claim | luggage |
| 🛅 | 1F6C5 | left luggage | luggage |
| ⚠️ | 26A0 FE0F | warning | warning |
| 🚸 | 1F6B8 | children crossing | directions_walk |
| ⛔ | 26D4 | no entry | block |
| 🚫 | 1F6AB | prohibited | block |
| 🚳 | 1F6B3 | no bicycles | block |
| 🚭 | 1F6AD | no smoking | smoke_free |
| 🚯 | 1F6AF | no littering | block |
| 🚱 | 1F6B1 | non-potable water | block |
| 🚷 | 1F6B7 | no pedestrians | block |
| 📵 | 1F4F5 | no mobile phones | mobile_off |
| 🔞 | 1F51E | no one under eighteen | no_adult_content |
| ☢️ | 2622 FE0F | radioactive | warning |
| ☣️ | 2623 FE0F | biohazard | coronavirus |
| ⬆️ | 2B06 FE0F | up arrow | arrow_upward |
| ↗️ | 2197 FE0F | up-right arrow | north_east |
| ➡️ | 27A1 FE0F | right arrow | arrow_forward |
| ↘️ | 2198 FE0F | down-right arrow | south_east |
| ⬇️ | 2B07 FE0F | down arrow | arrow_downward |
| ↙️ | 2199 FE0F | down-left arrow | south_west |
| ⬅️ | 2B05 FE0F | left arrow | arrow_back |
| ↖️ | 2196 FE0F | up-left arrow | north_west |
| ↕️ | 2195 FE0F | up-down arrow | swap_vert |
| ↔️ | 2194 FE0F | left-right arrow | arrow_range |
| ↩️ | 21A9 FE0F | right arrow curving left | undo |
| ↪️ | 21AA FE0F | left arrow curving right | redo |
| ⤴️ | 2934 FE0F | right arrow curving up | turn_slight_right |
| ⤵️ | 2935 FE0F | right arrow curving down | turn_right |
| 🔃 | 1F503 | clockwise vertical arrows | autorenew |
| 🔄 | 1F504 | counterclockwise arrows button | autorenew |
| 🔙 | 1F519 | BACK arrow | keyboard_backspace |
| 🔚 | 1F51A | END arrow | last_page |
| 🔛 | 1F51B | ON! arrow | toggle_on |
| 🔜 | 1F51C | SOON arrow | schedule |
| 🔝 | 1F51D | TOP arrow | vertical_align_top |
| 🛐 | 1F6D0 | place of worship | synagogue |
| ⚛️ | 269B FE0F | atom symbol | science |
| 🕉️ | 1F549 FE0F | om | self_improvement |
| ✡️ | 2721 FE0F | star of David | hexagon |
| ☸️ | 2638 FE0F | wheel of dharma | settings |
| ☯️ | 262F FE0F | yin yang | contrast |
| ✝️ | 271D FE0F | latin cross | church |
| ☦️ | 2626 FE0F | orthodox cross | church |
| ☪️ | 262A FE0F | star and crescent | dark_mode |
| ☮️ | 262E FE0F | peace symbol | spa |
| 🕎 | 1F54E | menorah | synagogue |
| 🔯 | 1F52F | dotted six-pointed star | star |
| 🪯 | 1FAAF | khanda | self_improvement |
| ♈ | 2648 | Aries | auto_awesome |
| ♉ | 2649 | Taurus | auto_awesome |
| ♊ | 264A | Gemini | auto_awesome |
| ♋ | 264B | Cancer | auto_awesome |
| ♌ | 264C | Leo | auto_awesome |
| ♍ | 264D | Virgo | auto_awesome |
| ♎ | 264E | Libra | auto_awesome |
| ♏ | 264F | Scorpio | auto_awesome |
| ♐ | 2650 | Sagittarius | auto_awesome |
| ♑ | 2651 | Capricorn | auto_awesome |
| ♒ | 2652 | Aquarius | auto_awesome |
| ♓ | 2653 | Pisces | auto_awesome |
| ⛎ | 26CE | Ophiuchus | auto_awesome |
| 🔀 | 1F500 | shuffle tracks button | shuffle |
| 🔁 | 1F501 | repeat button | repeat |
| 🔂 | 1F502 | repeat single button | repeat_one |
| ▶️ | 25B6 FE0F | play button | play_arrow:filled |
| ⏩ | 23E9 | fast-forward button | fast_forward |
| ⏭️ | 23ED FE0F | next track button | skip_next |
| ⏯️ | 23EF FE0F | play or pause button | play_pause |
| ◀️ | 25C0 FE0F | reverse button | play_arrow:filled:mirrored |
| ⏪ | 23EA | fast reverse button | fast_rewind |
| ⏮️ | 23EE FE0F | last track button | skip_previous |
| 🔼 | 1F53C | upwards button | keyboard_arrow_up |
| ⏫ | 23EB | fast up button | keyboard_double_arrow_up |
| 🔽 | 1F53D | downwards button | keyboard_arrow_down |
| ⏬ | 23EC | fast down button | keyboard_double_arrow_down |
| ⏸️ | 23F8 FE0F | pause button | pause |
| ⏹️ | 23F9 FE0F | stop button | stop |
| ⏺️ | 23FA FE0F | record button | fiber_manual_record |
| ⏏️ | 23CF FE0F | eject button | eject |
| 🎦 | 1F3A6 | cinema | movie |
| 🔅 | 1F505 | dim button | brightness_low |
| 🔆 | 1F506 | bright button | brightness_high |
| 📶 | 1F4F6 | antenna bars | signal_cellular_alt |
| 🛜 | 1F6DC | wireless | wifi |
| 📳 | 1F4F3 | vibration mode | vibration |
| 📴 | 1F4F4 | mobile phone off | mobile_off |
| ♀️ | 2640 FE0F | female sign | female |
| ♂️ | 2642 FE0F | male sign | male |
| ⚧️ | 26A7 FE0F | transgender symbol | transgender |
| ✖️ | 2716 FE0F | multiply | close |
| ➕ | 2795 | plus | add |
| ➖ | 2796 | minus | remove |
| ➗ | 2797 | divide | calculate |
| 🟰 | 1F7F0 | heavy equals sign | equal |
| ♾️ | 267E FE0F | infinity | all_inclusive |
| ‼️ | 203C FE0F | double exclamation mark | priority_high |
| ⁉️ | 2049 FE0F | exclamation question mark | priority_high |
| … | 2026 | horizontal ellipsis | more_horiz |
| ⋯ | 22EF | midline horizontal ellipsis | more_horiz |
| ⋮ | 22EE | vertical ellipsis | more_vert |
| ❓ | 2753 | red question mark | question_mark |
| ❔ | 2754 | white question mark | question_mark |
| ❕ | 2755 | white exclamation mark | priority_high |
| ❗ | 2757 | red exclamation mark | priority_high |
| 〰️ | 3030 FE0F | wavy dash | waves |
| 💱 | 1F4B1 | currency exchange | currency_exchange |
| 💲 | 1F4B2 | heavy dollar sign | attach_money |
| ⚕️ | 2695 FE0F | medical symbol | medical_services |
| ♻️ | 267B FE0F | recycling symbol | recycling |
| ⚜️ | 269C FE0F | fleur-de-lis | local_florist |
| 🔱 | 1F531 | trident emblem | anchor |
| 📛 | 1F4DB | name badge | badge |
| 🔰 | 1F530 | Japanese symbol for beginner | new_releases |
| ⭕ | 2B55 | hollow red circle | circle:outlined |
| ✅ | 2705 | check mark button | check_circle |
| ☑️ | 2611 FE0F | check box with check | check_box |
| ✔️ | 2714 FE0F | check mark | check |
| ❌ | 274C | cross mark | cancel |
| ❎ | 274E | cross mark button | disabled_by_default |
| ➰ | 27B0 | curly loop | gesture |
| ➿ | 27BF | double curly loop | gesture |
| 〽️ | 303D FE0F | part alternation mark | timeline |
| ✳️ | 2733 FE0F | eight-spoked asterisk | emergency |
| ✴️ | 2734 FE0F | eight-pointed star | emergency |
| ❇️ | 2747 FE0F | sparkle | auto_awesome |
| ©️ | 00A9 FE0F | copyright | copyright |
| ®️ | 00AE FE0F | registered | app_registration |
| ™️ | 2122 FE0F | trade mark | sell |
| 🫟 | 1FADF | splatter | blur_on |
| #️⃣ | 0023 FE0F 20E3 | keycap: # | tag |
| *️⃣ | 002A FE0F 20E3 | keycap: * | emergency |
| 0️⃣ | 0030 FE0F 20E3 | keycap: 0 | counter_0 |
| 1️⃣ | 0031 FE0F 20E3 | keycap: 1 | counter_1 |
| 2️⃣ | 0032 FE0F 20E3 | keycap: 2 | counter_2 |
| 3️⃣ | 0033 FE0F 20E3 | keycap: 3 | counter_3 |
| 4️⃣ | 0034 FE0F 20E3 | keycap: 4 | counter_4 |
| 5️⃣ | 0035 FE0F 20E3 | keycap: 5 | counter_5 |
| 6️⃣ | 0036 FE0F 20E3 | keycap: 6 | counter_6 |
| 7️⃣ | 0037 FE0F 20E3 | keycap: 7 | counter_7 |
| 8️⃣ | 0038 FE0F 20E3 | keycap: 8 | counter_8 |
| 9️⃣ | 0039 FE0F 20E3 | keycap: 9 | counter_9 |
| 🔟 | 1F51F | keycap: 10 | filter_9_plus |
| 🔠 | 1F520 | input latin uppercase | abc |
| 🔡 | 1F521 | input latin lowercase | abc |
| 🔢 | 1F522 | input numbers | 123 |
| 🔣 | 1F523 | input symbols | emoji_symbols |
| 🔤 | 1F524 | input latin letters | abc |
| 🅰️ | 1F170 FE0F | A button (blood type) | bloodtype |
| 🆎 | 1F18E | AB button (blood type) | bloodtype |
| 🅱️ | 1F171 FE0F | B button (blood type) | bloodtype |
| 🆑 | 1F191 | CL button | clear_all |
| 🆒 | 1F192 | COOL button | ac_unit |
| 🆓 | 1F193 | FREE button | money_off |
| ℹ️ | 2139 FE0F | information | info |
| 🆔 | 1F194 | ID button | badge |
| Ⓜ️ | 24C2 FE0F | circled M | subway |
| 🆕 | 1F195 | NEW button | fiber_new |
| 🆖 | 1F196 | NG button | report |
| 🅾️ | 1F17E FE0F | O button (blood type) | bloodtype |
| 🆗 | 1F197 | OK button | check_circle |
| 🅿️ | 1F17F FE0F | P button | local_parking |
| 🆘 | 1F198 | SOS button | sos |
| 🆙 | 1F199 | UP! button | arrow_circle_up |
| 🆚 | 1F19A | VS button | compare_arrows |
| 🈁 | 1F201 | Japanese “here” button | pin_drop |
| 🈂️ | 1F202 FE0F | Japanese “service charge” button | room_service |
| 🈷️ | 1F237 FE0F | Japanese “monthly amount” button | calendar_month |
| 🈶 | 1F236 | Japanese “not free of charge” button | paid |
| 🈯 | 1F22F | Japanese “reserved” button | bookmark |
| 🉐 | 1F250 | Japanese “bargain” button | percent_discount |
| 🈹 | 1F239 | Japanese “discount” button | percent_discount |
| 🈚 | 1F21A | Japanese “free of charge” button | money_off |
| 🈲 | 1F232 | Japanese “prohibited” button | block |
| 🉑 | 1F251 | Japanese “acceptable” button | check_circle |
| 🈸 | 1F238 | Japanese “application” button | edit_document |
| 🈴 | 1F234 | Japanese “passing grade” button | grade |
| 🈳 | 1F233 | Japanese “vacancy” button | meeting_room |
| ㊗️ | 3297 FE0F | Japanese “congratulations” button | celebration |
| ㊙️ | 3299 FE0F | Japanese “secret” button | lock |
| 🈺 | 1F23A | Japanese “open for business” button | storefront |
| 🈵 | 1F235 | Japanese “no vacancy” button | no_meeting_room |
| 🔴 | 1F534 | red circle | circle:filled |
| 🟠 | 1F7E0 | orange circle | circle:filled |
| 🟡 | 1F7E1 | yellow circle | circle:filled |
| 🟢 | 1F7E2 | green circle | circle:filled |
| 🔵 | 1F535 | blue circle | circle:filled |
| 🟣 | 1F7E3 | purple circle | circle:filled |
| 🟤 | 1F7E4 | brown circle | circle:filled |
| ⚫ | 26AB | black circle | circle:filled |
| ⚪ | 26AA | white circle | circle:outlined |
| 🟥 | 1F7E5 | red square | square:filled |
| 🟧 | 1F7E7 | orange square | square:filled |
| 🟨 | 1F7E8 | yellow square | square:filled |
| 🟩 | 1F7E9 | green square | square:filled |
| 🟦 | 1F7E6 | blue square | square:filled |
| 🟪 | 1F7EA | purple square | square:filled |
| 🟫 | 1F7EB | brown square | square:filled |
| ⬛ | 2B1B | black large square | square:filled |
| ⬜ | 2B1C | white large square | square:outlined |
| ◼️ | 25FC FE0F | black medium square | square:filled |
| ◻️ | 25FB FE0F | white medium square | square:outlined |
| ◾ | 25FE | black medium-small square | square:filled |
| ◽ | 25FD | white medium-small square | square:outlined |
| ▪️ | 25AA FE0F | black small square | square:filled |
| ▫️ | 25AB FE0F | white small square | square:outlined |
| 🔶 | 1F536 | large orange diamond | diamond:filled |
| 🔷 | 1F537 | large blue diamond | diamond:filled |
| 🔸 | 1F538 | small orange diamond | diamond:filled |
| 🔹 | 1F539 | small blue diamond | diamond:filled |
| 🔺 | 1F53A | red triangle pointed up | change_history:filled |
| 🔻 | 1F53B | red triangle pointed down | arrow_drop_down:filled |
| 💠 | 1F4A0 | diamond with a dot | diamond:filled |
| 🔘 | 1F518 | radio button | radio_button_checked |
| 🔳 | 1F533 | white square button | check_box_outline_blank:outlined |
| 🔲 | 1F532 | black square button | check_box_outline_blank:outlined |
| ★ | 2605 | black star | star:filled |
| ☆ | 2606 | white star | star:outlined |
| ☇ | 2607 | lightning | thunderstorm |
| ☈ | 2608 | thunderstorm | thunderstorm |
| ☉ | 2609 | sun | wb_sunny |
| ☊ | 260A | ascending node | orbit |
| ☋ | 260B | descending node | orbit |
| ☌ | 260C | conjunction | orbit |
| ☍ | 260D | opposition | orbit |
| ☏ | 260F | white telephone | call |
| ☐ | 2610 | ballot box | check_box_outline_blank |
| ☒ | 2612 | ballot box with x | disabled_by_default |
| ☓ | 2613 | saltire | close |
| ☖ | 2616 | white shogi piece | chess_pawn:outlined |
| ☗ | 2617 | black shogi piece | chess_pawn:filled |
| ☙ | 2619 | reversed rotated floral heart bullet | favorite |
| ☚ | 261A | black left pointing index | arrow_back |
| ☛ | 261B | black right pointing index | arrow_forward |
| ☜ | 261C | white left pointing index | arrow_back |
| ☞ | 261E | white right pointing index | arrow_forward |
| ☟ | 261F | white down pointing index | arrow_downward |
| ☡ | 2621 | caution sign | warning |
| ☤ | 2624 | caduceus | medical_services |
| ☥ | 2625 | ankh | church |
| ☧ | 2627 | chi rho | church |
| ☨ | 2628 | cross of lorraine | church |
| ☩ | 2629 | cross of jerusalem | church |
| ☫ | 262B | farsi symbol | medical_services |
| ☬ | 262C | adi shakti | church |
| ☭ | 262D | hammer and sickle | construction |
| ☰ | 2630 | trigram for heaven | menu |
| ☱ | 2631 | trigram for lake | menu |
| ☲ | 2632 | trigram for fire | menu |
| ☳ | 2633 | trigram for thunder | menu |
| ☴ | 2634 | trigram for wind | menu |
| ☵ | 2635 | trigram for water | menu |
| ☶ | 2636 | trigram for mountain | menu |
| ☷ | 2637 | trigram for earth | menu |
| ☻ | 263B | black smiling face | sentiment_satisfied:filled |
| ☼ | 263C | white sun with rays | light_mode |
| ☽ | 263D | first quarter moon | dark_mode |
| ☾ | 263E | last quarter moon | dark_mode |
| ☿ | 263F | mercury | planet |
| ♁ | 2641 | earth | public |
| ♃ | 2643 | jupiter | planet |
| ♄ | 2644 | saturn | planet |
| ♅ | 2645 | uranus | planet |
| ♆ | 2646 | neptune | planet |
| ♇ | 2647 | pluto | planet |
| ♔ | 2654 | white chess king | chess_king:outlined |
| ♕ | 2655 | white chess queen | chess_queen:outlined |
| ♖ | 2656 | white chess rook | chess_rook:outlined |
| ♗ | 2657 | white chess bishop | chess_bishop:outlined |
| ♘ | 2658 | white chess knight | chess_knight:outlined |
| ♙ | 2659 | white chess pawn | chess_pawn:outlined |
| ♚ | 265A | black chess king | chess_king:filled |
| ♛ | 265B | black chess queen | chess_queen:filled |
| ♜ | 265C | black chess rook | chess_rook:filled |
| ♝ | 265D | black chess bishop | chess_bishop:filled |
| ♞ | 265E | black chess knight | chess_knight:filled |
| ♡ | 2661 | white heart suit | favorite:outlined |
| ♢ | 2662 | white diamond suit | diamond:outlined |
| ♤ | 2664 | white spade suit | playing_cards |
| ♧ | 2667 | white club suit | playing_cards |
| ♩ | 2669 | quarter note | music_note |
| ♪ | 266A | eighth note | music_note |
| ♫ | 266B | beamed eighth notes | queue_music |
| ♬ | 266C | beamed sixteenth notes | queue_music |
| ♭ | 266D | music flat sign | music_note |
| ♮ | 266E | music natural sign | music_note |
| ♯ | 266F | music sharp sign | music_note |
| ♰ | 2670 | west syriac cross | church |
| ♱ | 2671 | east syriac cross | church |
| ♲ | 2672 | universal recycling symbol | recycling |
| ♳ | 2673 | recycling symbol for type-1 plastics | recycling |
| ♴ | 2674 | recycling symbol for type-2 plastics | recycling |
| ♵ | 2675 | recycling symbol for type-3 plastics | recycling |
| ♶ | 2676 | recycling symbol for type-4 plastics | recycling |
| ♷ | 2677 | recycling symbol for type-5 plastics | recycling |
| ♸ | 2678 | recycling symbol for type-6 plastics | recycling |
| ♹ | 2679 | recycling symbol for type-7 plastics | recycling |
| ♺ | 267A | recycling symbol for generic materials | recycling |
| ♼ | 267C | recycled paper symbol | recycling |
| ♽ | 267D | partially-recycled paper symbol | recycling |
| ⚀ | 2680 | die face-1 | looks_one |
| ⚁ | 2681 | die face-2 | looks_two |
| ⚂ | 2682 | die face-3 | looks_3 |
| ⚃ | 2683 | die face-4 | looks_4 |
| ⚄ | 2684 | die face-5 | looks_5 |
| ⚅ | 2685 | die face-6 | looks_6 |
| ⚆ | 2686 | white circle with dot right | adjust |
| ⚇ | 2687 | white circle with two dots | adjust |
| ⚈ | 2688 | black circle with white dot right | trip_origin |
| ⚉ | 2689 | black circle with two white dots | trip_origin |
| ⚊ | 268A | monogram for yang | remove |
| ⚋ | 268B | monogram for yin | remove |
| ⚌ | 268C | digram for greater yang | drag_handle |
| ⚍ | 268D | digram for lesser yin | drag_handle |
| ⚎ | 268E | digram for lesser yang | drag_handle |
| ⚏ | 268F | digram for greater yin | drag_handle |
| ⚐ | 2690 | white flag | outlined_flag |
| ⚑ | 2691 | black flag | flag:filled |
| ⚘ | 2698 | flower | local_florist |
| ⚚ | 269A | staff of hermes | medical_services |
| ⚝ | 269D | outlined white star | star:outlined |
| ⚞ | 269E | three lines converging right | call_merge |
| ⚟ | 269F | three lines converging left | call_merge |
| ⚢ | 26A2 | doubled female sign | female |
| ⚣ | 26A3 | doubled male sign | male |
| ⚤ | 26A4 | interlocked female and male sign | wc |
| ⚥ | 26A5 | male and female sign | wc |
| ⚦ | 26A6 | male with stroke sign | male |
| ⚨ | 26A8 | vertical male with stroke sign | male |
| ⚩ | 26A9 | horizontal male with stroke sign | male |
| ⚬ | 26AC | medium small white circle | circle:outlined |
| ⚭ | 26AD | marriage symbol | favorite |
| ⚮ | 26AE | divorce symbol | heart_broken |
| ⚯ | 26AF | unmarried partnership symbol | link |
| ⚲ | 26B2 | neuter | transgender |
| ⚳ | 26B3 | ceres | public |
| ⚴ | 26B4 | pallas | public |
| ⚵ | 26B5 | juno | public |
| ⚶ | 26B6 | vesta | public |
| ⚷ | 26B7 | chiron | public |
| ⚸ | 26B8 | black moon lilith | public |
| ⚹ | 26B9 | sextile | change_history |
| ⚺ | 26BA | semisextile | change_history |
| ⚻ | 26BB | quincunx | change_history |
| ⚼ | 26BC | sesquiquadrate | change_history |
| ⚿ | 26BF | squared key | key |
| ⛀ | 26C0 | white draughts man | circle:outlined |
| ⛁ | 26C1 | white draughts king | circle:outlined |
| ⛂ | 26C2 | black draughts man | circle:filled |
| ⛃ | 26C3 | black draughts king | circle:filled |
| ⛆ | 26C6 | rain | rainy |
| ⛇ | 26C7 | black snowman | ac_unit |
| ⛉ | 26C9 | turned white shogi piece | chess_pawn |
| ⛊ | 26CA | turned black shogi piece | chess_pawn |
| ⛋ | 26CB | white diamond in square | diamond:outlined |
| ⛌ | 26CC | crossing lanes | alt_route |
| ⛍ | 26CD | disabled car | car_crash |
| ⛐ | 26D0 | car sliding | car_crash |
| ⛒ | 26D2 | circled crossing lanes | alt_route |
| ⛕ | 26D5 | alternate one-way left way traffic | swap_horiz |
| ⛖ | 26D6 | black two-way left way traffic | swap_horiz |
| ⛗ | 26D7 | white two-way left way traffic | swap_horiz |
| ⛘ | 26D8 | black left lane merge | merge |
| ⛙ | 26D9 | white left lane merge | merge |
| ⛚ | 26DA | drive slow sign | speed |
| ⛛ | 26DB | heavy white down-pointing triangle | arrow_drop_down:filled |
| ⛜ | 26DC | left closed entry | login |
| ⛝ | 26DD | squared saltire | disabled_by_default |
| ⛞ | 26DE | falling diagonal in white circle in black square | block |
| ⛟ | 26DF | black truck | local_shipping |
| ⛠ | 26E0 | restricted left entry-1 | block |
| ⛡ | 26E1 | restricted left entry-2 | block |
| ⛢ | 26E2 | astronomical symbol for uranus | planet |
| ⛣ | 26E3 | heavy circle with stroke and two dots above | trip_origin |
| ⛤ | 26E4 | pentagram | star |
| ⛥ | 26E5 | right-handed interlaced pentagram | star |
| ⛦ | 26E6 | left-handed interlaced pentagram | star |
| ⛧ | 26E7 | inverted pentagram | star |
| ⛨ | 26E8 | black cross on shield | shield |
| ⛫ | 26EB | castle | castle |
| ⛬ | 26EC | historic site | museum |
| ⛭ | 26ED | gear without hub | settings |
| ⛮ | 26EE | gear with handles | settings |
| ⛯ | 26EF | map symbol for lighthouse | light_mode |
| ⛶ | 26F6 | square four corners | crop_free |
| ⛻ | 26FB | japanese bank symbol | account_balance |
| ⛼ | 26FC | headstone graveyard symbol | church |
| ⛾ | 26FE | cup on black square | local_cafe |
| ⛿ | 26FF | white flag with horizontal middle black stripe | flag |
| ✀ | 2700 | black safety scissors | content_cut |
| ✁ | 2701 | upper blade scissors | content_cut |
| ✃ | 2703 | lower blade scissors | content_cut |
| ✄ | 2704 | white scissors | content_cut |
| ✆ | 2706 | telephone location sign | phone_in_talk |
| ✇ | 2707 | tape drive | album |
| ✎ | 270E | lower right pencil | edit |
| ✐ | 2710 | upper right pencil | edit |
| ✑ | 2711 | white nib | ink_pen |
| ✓ | 2713 | check mark | check |
| ✕ | 2715 | multiplication x | close |
| ✗ | 2717 | ballot x | close |
| ✘ | 2718 | heavy ballot x | close |
| ✙ | 2719 | outlined greek cross | add |
| ✚ | 271A | heavy greek cross | add |
| ✛ | 271B | open centre cross | add |
| ✜ | 271C | heavy open centre cross | add |
| ✞ | 271E | shadowed white latin cross | church |
| ✟ | 271F | outlined latin cross | church |
| ✠ | 2720 | maltese cross | church |
| ✢ | 2722 | four teardrop-spoked asterisk | emergency |
| ✣ | 2723 | four balloon-spoked asterisk | emergency |
| ✤ | 2724 | heavy four balloon-spoked asterisk | emergency |
| ✥ | 2725 | four club-spoked asterisk | emergency |
| ✦ | 2726 | black four pointed star | star:filled |
| ✧ | 2727 | white four pointed star | star:outlined |
| ✩ | 2729 | stress outlined white star | star:outlined |
| ✪ | 272A | circled white star | stars |
| ✫ | 272B | open centre black star | star:outlined |
| ✬ | 272C | black centre white star | star:filled |
| ✭ | 272D | outlined black star | star:outlined |
| ✮ | 272E | heavy outlined black star | star:filled |
| ✯ | 272F | pinwheel star | star:filled |
| ✰ | 2730 | shadowed white star | star:outlined |
| ✱ | 2731 | heavy asterisk | emergency |
| ✲ | 2732 | open centre asterisk | emergency |
| ✵ | 2735 | eight pointed pinwheel star | emergency |
| ✶ | 2736 | six pointed black star | star:filled |
| ✷ | 2737 | eight pointed rectilinear black star | star:filled |
| ✸ | 2738 | heavy eight pointed rectilinear black star | star:filled |
| ✹ | 2739 | twelve pointed black star | star:filled |
| ✺ | 273A | sixteen pointed asterisk | star:filled |
| ✻ | 273B | teardrop-spoked asterisk | emergency |
| ✼ | 273C | open centre teardrop-spoked asterisk | emergency |
| ✽ | 273D | heavy teardrop-spoked asterisk | emergency |
| ✾ | 273E | six petalled black and white florette | local_florist |
| ✿ | 273F | black florette | local_florist |
| ❀ | 2740 | white florette | local_florist |
| ❁ | 2741 | eight petalled outlined black florette | local_florist |
| ❂ | 2742 | circled open centre eight pointed star | emergency |
| ❃ | 2743 | heavy teardrop-spoked pinwheel asterisk | emergency |
| ❅ | 2745 | tight trifoliate snowflake | ac_unit |
| ❆ | 2746 | heavy chevron snowflake | ac_unit |
| ❈ | 2748 | heavy sparkle | auto_awesome |
| ❉ | 2749 | balloon-spoked asterisk | emergency |
| ❊ | 274A | eight teardrop-spoked propeller asterisk | emergency |
| ❋ | 274B | heavy eight teardrop-spoked propeller asterisk | emergency |
| ❍ | 274D | shadowed white circle | circle:outlined |
| ❏ | 274F | lower right drop-shadowed white square | check_box_outline_blank:outlined |
| ❐ | 2750 | upper right drop-shadowed white square | check_box_outline_blank:outlined |
| ❑ | 2751 | lower right shadowed white square | check_box_outline_blank:outlined |
| ❒ | 2752 | upper right shadowed white square | check_box_outline_blank:outlined |
| ❖ | 2756 | black diamond minus white x | diamond:filled |
| ❘ | 2758 | light vertical bar | more_vert |
| ❙ | 2759 | medium vertical bar | more_vert |
| ❚ | 275A | heavy vertical bar | more_vert |
| ❛ | 275B | heavy single turned comma quotation mark ornament | format_quote |
| ❜ | 275C | heavy single comma quotation mark ornament | format_quote |
| ❝ | 275D | heavy double turned comma quotation mark ornament | format_quote |
| ❞ | 275E | heavy double comma quotation mark ornament | format_quote |
| ❟ | 275F | heavy low single comma quotation mark ornament | format_quote |
| ❠ | 2760 | heavy low double comma quotation mark ornament | format_quote |
| ❡ | 2761 | curved stem paragraph sign ornament | format_paragraph |
| ❢ | 2762 | heavy exclamation mark ornament | priority_high |
| ❥ | 2765 | rotated heavy black heart bullet | favorite |
| ❦ | 2766 | floral heart | favorite |
| ❧ | 2767 | rotated floral heart bullet | favorite |
| ❨ | 2768 | medium left parenthesis ornament | data_object |
| ❩ | 2769 | medium right parenthesis ornament | data_object |
| ❪ | 276A | medium flattened left parenthesis ornament | data_object |
| ❫ | 276B | medium flattened right parenthesis ornament | data_object |
| ❬ | 276C | medium left-pointing angle bracket ornament | chevron_left |
| ❭ | 276D | medium right-pointing angle bracket ornament | chevron_right |
| ❮ | 276E | heavy left-pointing angle quotation mark ornament | chevron_left |
| ❯ | 276F | heavy right-pointing angle quotation mark ornament | chevron_right |
| ❰ | 2770 | heavy left-pointing angle bracket ornament | chevron_left |
| ❱ | 2771 | heavy right-pointing angle bracket ornament | chevron_right |
| ❲ | 2772 | light left tortoise shell bracket ornament | data_object |
| ❳ | 2773 | light right tortoise shell bracket ornament | data_object |
| ❴ | 2774 | medium left curly bracket ornament | data_object |
| ❵ | 2775 | medium right curly bracket ornament | data_object |
| ❶ | 2776 | dingbat negative circled digit one | counter_1 |
| ❷ | 2777 | dingbat negative circled digit two | counter_2 |
| ❸ | 2778 | dingbat negative circled digit three | counter_3 |
| ❹ | 2779 | dingbat negative circled digit four | counter_4 |
| ❺ | 277A | dingbat negative circled digit five | counter_5 |
| ❻ | 277B | dingbat negative circled digit six | counter_6 |
| ❼ | 277C | dingbat negative circled digit seven | counter_7 |
| ❽ | 277D | dingbat negative circled digit eight | counter_8 |
| ❾ | 277E | dingbat negative circled digit nine | counter_9 |
| ❿ | 277F | dingbat negative circled number ten | filter_9_plus |
| ➀ | 2780 | dingbat circled sans-serif digit one | counter_1 |
| ➁ | 2781 | dingbat circled sans-serif digit two | counter_2 |
| ➂ | 2782 | dingbat circled sans-serif digit three | counter_3 |
| ➃ | 2783 | dingbat circled sans-serif digit four | counter_4 |
| ➄ | 2784 | dingbat circled sans-serif digit five | counter_5 |
| ➅ | 2785 | dingbat circled sans-serif digit six | counter_6 |
| ➆ | 2786 | dingbat circled sans-serif digit seven | counter_7 |
| ➇ | 2787 | dingbat circled sans-serif digit eight | counter_8 |
| ➈ | 2788 | dingbat circled sans-serif digit nine | counter_9 |
| ➉ | 2789 | dingbat circled sans-serif number ten | filter_9_plus |
| ➊ | 278A | dingbat negative circled sans-serif digit one | counter_1 |
| ➋ | 278B | dingbat negative circled sans-serif digit two | counter_2 |
| ➌ | 278C | dingbat negative circled sans-serif digit three | counter_3 |
| ➍ | 278D | dingbat negative circled sans-serif digit four | counter_4 |
| ➎ | 278E | dingbat negative circled sans-serif digit five | counter_5 |
| ➏ | 278F | dingbat negative circled sans-serif digit six | counter_6 |
| ➐ | 2790 | dingbat negative circled sans-serif digit seven | counter_7 |
| ➑ | 2791 | dingbat negative circled sans-serif digit eight | counter_8 |
| ➒ | 2792 | dingbat negative circled sans-serif digit nine | counter_9 |
| ➓ | 2793 | dingbat negative circled sans-serif number ten | filter_9_plus |
| ➔ | 2794 | heavy wide-headed rightwards arrow | arrow_forward |
| ➘ | 2798 | heavy south east arrow | south_east |
| ➙ | 2799 | heavy rightwards arrow | arrow_forward |
| ➚ | 279A | heavy north east arrow | north_east |
| ➛ | 279B | drafting point rightwards arrow | arrow_forward |
| ➜ | 279C | heavy round-tipped rightwards arrow | arrow_forward |
| ➝ | 279D | triangle-headed rightwards arrow | arrow_forward |
| ➞ | 279E | heavy triangle-headed rightwards arrow | arrow_forward |
| ➟ | 279F | dashed triangle-headed rightwards arrow | arrow_forward |
| ➠ | 27A0 | heavy dashed triangle-headed rightwards arrow | arrow_forward |
| ➢ | 27A2 | three-d top-lighted rightwards arrowhead | arrow_forward |
| ➣ | 27A3 | three-d bottom-lighted rightwards arrowhead | arrow_forward |
| ➤ | 27A4 | black rightwards arrowhead | arrow_forward |
| ➥ | 27A5 | heavy black curved downwards and rightwards arrow | subdirectory_arrow_right |
| ➦ | 27A6 | heavy black curved upwards and rightwards arrow | turn_slight_right |
| ➧ | 27A7 | squat black rightwards arrow | arrow_forward |
| ➨ | 27A8 | heavy concave-pointed black rightwards arrow | arrow_forward |
| ➩ | 27A9 | right-shaded white rightwards arrow | arrow_forward |
| ➪ | 27AA | left-shaded white rightwards arrow | arrow_forward |
| ➫ | 27AB | back-tilted shadowed white rightwards arrow | arrow_forward |
| ➬ | 27AC | front-tilted shadowed white rightwards arrow | arrow_forward |
| ➭ | 27AD | heavy lower right-shadowed white rightwards arrow | arrow_forward |
| ➮ | 27AE | heavy upper right-shadowed white rightwards arrow | arrow_forward |
| ➯ | 27AF | notched lower right-shadowed white rightwards arrow | arrow_forward |
| ➱ | 27B1 | notched upper right-shadowed white rightwards arrow | arrow_forward |
| ➲ | 27B2 | circled heavy white rightwards arrow | arrow_circle_right |
| ➳ | 27B3 | white-feathered rightwards arrow | arrow_forward |
| ➴ | 27B4 | black-feathered south east arrow | south_east |
| ➵ | 27B5 | black-feathered rightwards arrow | arrow_forward |
| ➶ | 27B6 | black-feathered north east arrow | north_east |
| ➷ | 27B7 | heavy black-feathered south east arrow | south_east |
| ➸ | 27B8 | heavy black-feathered rightwards arrow | arrow_forward |
| ➹ | 27B9 | heavy black-feathered north east arrow | north_east |
| ➺ | 27BA | teardrop-barbed rightwards arrow | arrow_forward |
| ➻ | 27BB | heavy teardrop-shanked rightwards arrow | arrow_forward |
| ➼ | 27BC | wedge-tailed rightwards arrow | arrow_forward |
| ➽ | 27BD | heavy wedge-tailed rightwards arrow | arrow_forward |
| ➾ | 27BE | open-outlined rightwards arrow | arrow_forward |
| ← | 2190 | leftwards arrow | arrow_back |
| ↑ | 2191 | upwards arrow | arrow_upward |
| → | 2192 | rightwards arrow | arrow_forward |
| ↓ | 2193 | downwards arrow | arrow_downward |
| ↚ | 219A | leftwards arrow with stroke | arrow_back |
| ↛ | 219B | rightwards arrow with stroke | arrow_forward |
| ↜ | 219C | leftwards wave arrow | arrow_back |
| ↝ | 219D | rightwards wave arrow | arrow_forward |
| ↞ | 219E | leftwards two headed arrow | keyboard_double_arrow_left |
| ↟ | 219F | upwards two headed arrow | keyboard_double_arrow_up |
| ↠ | 21A0 | rightwards two headed arrow | keyboard_double_arrow_right |
| ↡ | 21A1 | downwards two headed arrow | keyboard_double_arrow_down |
| ↢ | 21A2 | leftwards arrow with tail | arrow_back |
| ↣ | 21A3 | rightwards arrow with tail | arrow_forward |
| ↤ | 21A4 | leftwards arrow from bar | keyboard_tab_rtl |
| ↥ | 21A5 | upwards arrow from bar | vertical_align_top |
| ↦ | 21A6 | rightwards arrow from bar | keyboard_tab |
| ↧ | 21A7 | downwards arrow from bar | vertical_align_bottom |
| ↨ | 21A8 | up down arrow with base | swap_vert |
| ↫ | 21AB | leftwards arrow with loop | arrow_back |
| ↬ | 21AC | rightwards arrow with loop | arrow_forward |
| ↭ | 21AD | left right wave arrow | arrow_range |
| ↮ | 21AE | left right arrow with stroke | swap_horiz |
| ↯ | 21AF | downwards zigzag arrow | bolt |
| ↰ | 21B0 | upwards arrow with tip leftwards | turn_left |
| ↱ | 21B1 | upwards arrow with tip rightwards | turn_right |
| ↲ | 21B2 | downwards arrow with tip leftwards | subdirectory_arrow_left |
| ↳ | 21B3 | downwards arrow with tip rightwards | subdirectory_arrow_right |
| ↴ | 21B4 | rightwards arrow with corner downwards | subdirectory_arrow_right |
| ↵ | 21B5 | downwards arrow with corner leftwards | keyboard_return |
| ↶ | 21B6 | anticlockwise top semicircle arrow | undo |
| ↷ | 21B7 | clockwise top semicircle arrow | redo |
| ↸ | 21B8 | north west arrow to long bar | north_west |
| ↹ | 21B9 | leftwards arrow to bar over rightwards arrow to bar | keyboard_tab |
| ↺ | 21BA | anticlockwise open circle arrow | rotate_left |
| ↻ | 21BB | clockwise open circle arrow | rotate_right |
| ↼ | 21BC | leftwards harpoon with barb upwards | arrow_back |
| ↽ | 21BD | leftwards harpoon with barb downwards | arrow_back |
| ↾ | 21BE | upwards harpoon with barb rightwards | arrow_upward |
| ↿ | 21BF | upwards harpoon with barb leftwards | arrow_upward |
| ⇀ | 21C0 | rightwards harpoon with barb upwards | arrow_forward |
| ⇁ | 21C1 | rightwards harpoon with barb downwards | arrow_forward |
| ⇂ | 21C2 | downwards harpoon with barb rightwards | arrow_downward |
| ⇃ | 21C3 | downwards harpoon with barb leftwards | arrow_downward |
| ⇄ | 21C4 | rightwards arrow over leftwards arrow | swap_horiz |
| ⇅ | 21C5 | upwards arrow leftwards of downwards arrow | swap_vert |
| ⇆ | 21C6 | leftwards arrow over rightwards arrow | swap_horiz |
| ⇇ | 21C7 | leftwards paired arrows | keyboard_double_arrow_left |
| ⇈ | 21C8 | upwards paired arrows | keyboard_double_arrow_up |
| ⇉ | 21C9 | rightwards paired arrows | keyboard_double_arrow_right |
| ⇊ | 21CA | downwards paired arrows | keyboard_double_arrow_down |
| ⇋ | 21CB | leftwards harpoon over rightwards harpoon | compare_arrows |
| ⇌ | 21CC | rightwards harpoon over leftwards harpoon | compare_arrows |
| ⇍ | 21CD | leftwards double arrow with stroke | arrow_back |
| ⇎ | 21CE | left right double arrow with stroke | swap_horiz |
| ⇏ | 21CF | rightwards double arrow with stroke | arrow_forward |
| ⇐ | 21D0 | leftwards double arrow | arrow_back |
| ⇑ | 21D1 | upwards double arrow | arrow_upward |
| ⇒ | 21D2 | rightwards double arrow | arrow_forward |
| ⇓ | 21D3 | downwards double arrow | arrow_downward |
| ⇔ | 21D4 | left right double arrow | arrow_range |
| ⇕ | 21D5 | up down double arrow | swap_vert |
| ⇖ | 21D6 | north west double arrow | north_west |
| ⇗ | 21D7 | north east double arrow | north_east |
| ⇘ | 21D8 | south east double arrow | south_east |
| ⇙ | 21D9 | south west double arrow | south_west |
| ⇚ | 21DA | leftwards triple arrow | keyboard_double_arrow_left |
| ⇛ | 21DB | rightwards triple arrow | keyboard_double_arrow_right |
| ⇜ | 21DC | leftwards squiggle arrow | arrow_back |
| ⇝ | 21DD | rightwards squiggle arrow | arrow_forward |
| ⇞ | 21DE | upwards arrow with double stroke | arrow_upward |
| ⇟ | 21DF | downwards arrow with double stroke | arrow_downward |
| ⇠ | 21E0 | leftwards dashed arrow | arrow_back |
| ⇡ | 21E1 | upwards dashed arrow | arrow_upward |
| ⇢ | 21E2 | rightwards dashed arrow | arrow_forward |
| ⇣ | 21E3 | downwards dashed arrow | arrow_downward |
| ⇤ | 21E4 | leftwards arrow to bar | keyboard_tab_rtl |
| ⇥ | 21E5 | rightwards arrow to bar | keyboard_tab |
| ⇦ | 21E6 | leftwards white arrow | arrow_back |
| ⇧ | 21E7 | upwards white arrow | arrow_upward |
| ⇨ | 21E8 | rightwards white arrow | arrow_forward |
| ⇩ | 21E9 | downwards white arrow | arrow_downward |
| ⇪ | 21EA | upwards white arrow from bar | keyboard_capslock |
| ⇫ | 21EB | upwards white arrow on pedestal | keyboard_capslock |
| ⇬ | 21EC | upwards white arrow on pedestal with horizontal bar | keyboard_capslock |
| ⇭ | 21ED | upwards white arrow on pedestal with vertical bar | keyboard_capslock |
| ⇮ | 21EE | upwards white double arrow | keyboard_double_arrow_up |
| ⇯ | 21EF | upwards white double arrow on pedestal | keyboard_capslock |
| ⇰ | 21F0 | rightwards white arrow from wall | last_page |
| ⇱ | 21F1 | north west arrow to corner | north_west |
| ⇲ | 21F2 | south east arrow to corner | south_east |
| ⇳ | 21F3 | up down white arrow | swap_vert |
| ⇴ | 21F4 | right arrow with small circle | arrow_forward |
| ⇵ | 21F5 | downwards arrow leftwards of upwards arrow | swap_vert |
| ⇶ | 21F6 | three rightwards arrows | arrow_forward |
| ⇷ | 21F7 | leftwards arrow with vertical stroke | arrow_back |
| ⇸ | 21F8 | rightwards arrow with vertical stroke | arrow_forward |
| ⇹ | 21F9 | left right arrow with vertical stroke | swap_horiz |
| ⇺ | 21FA | leftwards arrow with double vertical stroke | arrow_back |
| ⇻ | 21FB | rightwards arrow with double vertical stroke | arrow_forward |
| ⇼ | 21FC | left right arrow with double vertical stroke | swap_horiz |
| ⇽ | 21FD | leftwards open-headed arrow | arrow_back |
| ⇾ | 21FE | rightwards open-headed arrow | arrow_forward |
| ⇿ | 21FF | left right open-headed arrow | arrow_range |
| ▀ | 2580 | upper half block | splitscreen_top:filled |
| ▁ | 2581 | lower one eighth block | square:outlined |
| ▂ | 2582 | lower one quarter block | square:outlined |
| ▃ | 2583 | lower three eighths block | splitscreen_bottom:filled |
| ▄ | 2584 | lower half block | splitscreen_bottom:filled |
| ▅ | 2585 | lower five eighths block | splitscreen_bottom:filled |
| ▆ | 2586 | lower three quarters block | square:filled |
| ▇ | 2587 | lower seven eighths block | square:filled |
| █ | 2588 | full block | square:filled |
| ▉ | 2589 | left seven eighths block | square:filled |
| ▊ | 258A | left three quarters block | square:filled |
| ▋ | 258B | left five eighths block | splitscreen_left:filled |
| ▌ | 258C | left half block | splitscreen_left:filled |
| ▍ | 258D | left three eighths block | splitscreen_left:filled |
| ▎ | 258E | left one quarter block | square:outlined |
| ▏ | 258F | left one eighth block | align_horizontal_left |
| ▐ | 2590 | right half block | splitscreen_right:filled |
| ░ | 2591 | light shade | square:outlined |
| ▒ | 2592 | medium shade | square:outlined |
| ▓ | 2593 | dark shade | square:filled |
| ▔ | 2594 | upper one eighth block | align_vertical_top |
| ▕ | 2595 | right one eighth block | align_horizontal_right |
| ▖ | 2596 | quadrant lower left | grid_view |
| ▗ | 2597 | quadrant lower right | grid_view |
| ▘ | 2598 | quadrant upper left | grid_view |
| ▙ | 2599 | quadrant upper left and lower left and lower right | grid_view |
| ▚ | 259A | quadrant upper left and lower right | view_quilt |
| ▛ | 259B | quadrant upper left and upper right and lower left | grid_view |
| ▜ | 259C | quadrant upper left and upper right and lower right | grid_view |
| ▝ | 259D | quadrant upper right | grid_view |
| ▞ | 259E | quadrant upper right and lower left | view_quilt |
| ▟ | 259F | quadrant upper right and lower left and lower right | grid_view |
| ■ | 25A0 | black square | square:filled |
| □ | 25A1 | white square | square:outlined |
| ▢ | 25A2 | white square with rounded corners | crop_square:outlined |
| ▣ | 25A3 | white square containing black small square | square_dot |
| ▤ | 25A4 | square with horizontal fill | view_headline |
| ▥ | 25A5 | square with vertical fill | view_column |
| ▦ | 25A6 | square with orthogonal crosshatch fill | grid_4x4 |
| ▧ | 25A7 | square with upper left to lower right fill | texture |
| ▨ | 25A8 | square with upper right to lower left fill | texture |
| ▩ | 25A9 | square with diagonal crosshatch fill | grid_on |
| ▬ | 25AC | black rectangle | rectangle:filled |
| ▭ | 25AD | white rectangle | rectangle:outlined |
| ▮ | 25AE | black vertical rectangle | crop_portrait:filled |
| ▯ | 25AF | white vertical rectangle | crop_portrait:outlined |
| ▰ | 25B0 | black parallelogram | rectangle:filled |
| ▱ | 25B1 | white parallelogram | rectangle:outlined |
| ▲ | 25B2 | black up-pointing triangle | arrow_drop_up:filled |
| △ | 25B3 | white up-pointing triangle | change_history:outlined |
| ▴ | 25B4 | black up-pointing small triangle | arrow_drop_up:filled |
| ▵ | 25B5 | white up-pointing small triangle | change_history:outlined |
| ▷ | 25B7 | white right-pointing triangle | play_arrow:outlined |
| ▸ | 25B8 | black right-pointing small triangle | arrow_right:filled |
| ▹ | 25B9 | white right-pointing small triangle | arrow_right:outlined |
| ► | 25BA | black right-pointing pointer | play_arrow:filled |
| ▻ | 25BB | white right-pointing pointer | play_arrow:outlined |
| ▼ | 25BC | black down-pointing triangle | arrow_drop_down:filled |
| ▽ | 25BD | white down-pointing triangle | arrow_drop_down:outlined |
| ▾ | 25BE | black down-pointing small triangle | arrow_drop_down:filled |
| ▿ | 25BF | white down-pointing small triangle | arrow_drop_down:outlined |
| ◁ | 25C1 | white left-pointing triangle | arrow_left:outlined |
| ◂ | 25C2 | black left-pointing small triangle | arrow_left:filled |
| ◃ | 25C3 | white left-pointing small triangle | arrow_left:outlined |
| ◄ | 25C4 | black left-pointing pointer | arrow_left:filled |
| ◅ | 25C5 | white left-pointing pointer | arrow_left:outlined |
| ◆ | 25C6 | black diamond | diamond:filled |
| ◇ | 25C7 | white diamond | diamond:outlined |
| ◈ | 25C8 | white diamond containing black small diamond | diamond_shine |
| ◉ | 25C9 | fisheye | radio_button_checked |
| ◊ | 25CA | lozenge | diamond:outlined |
| ○ | 25CB | white circle | circle:outlined |
| ◌ | 25CC | dotted circle | radio_button_unchecked |
| ◍ | 25CD | circle with vertical fill | contrast |
| ◎ | 25CE | bullseye | trip_origin |
| ● | 25CF | black circle | circle:filled |
| ◐ | 25D0 | circle with left half black | contrast |
| ◑ | 25D1 | circle with right half black | contrast |
| ◒ | 25D2 | circle with lower half black | tonality |
| ◓ | 25D3 | circle with upper half black | tonality |
| ◔ | 25D4 | circle with upper right quadrant black | data_usage |
| ◕ | 25D5 | circle with all but upper left quadrant black | incomplete_circle |
| ◖ | 25D6 | left half black circle | contrast |
| ◗ | 25D7 | right half black circle | contrast |
| ◘ | 25D8 | inverse bullet | circle:filled |
| ◙ | 25D9 | inverse white circle | radio_button_checked |
| ◚ | 25DA | upper half inverse white circle | contrast |
| ◛ | 25DB | lower half inverse white circle | contrast |
| ◜ | 25DC | upper left quadrant circular arc | incomplete_circle |
| ◝ | 25DD | upper right quadrant circular arc | incomplete_circle |
| ◞ | 25DE | lower right quadrant circular arc | incomplete_circle |
| ◟ | 25DF | lower left quadrant circular arc | incomplete_circle |
| ◠ | 25E0 | upper half circle | line_curve |
| ◡ | 25E1 | lower half circle | line_curve |
| ◢ | 25E2 | black lower right triangle | signal_cellular_4_bar:filled |
| ◣ | 25E3 | black lower left triangle | south_west |
| ◤ | 25E4 | black upper left triangle | north_west |
| ◥ | 25E5 | black upper right triangle | north_east |
| ◦ | 25E6 | white bullet | circle:outlined |
| ◧ | 25E7 | square with left half black | splitscreen_left |
| ◨ | 25E8 | square with right half black | splitscreen_right |
| ◩ | 25E9 | square with upper left diagonal half black | contrast_square |
| ◪ | 25EA | square with lower right diagonal half black | contrast_square |
| ◫ | 25EB | white square with vertical bisecting line | vertical_split |
| ◬ | 25EC | white up-pointing triangle with dot | change_history:outlined |
| ◭ | 25ED | up-pointing triangle with left half black | change_history:outlined |
| ◮ | 25EE | up-pointing triangle with right half black | change_history:outlined |
| ◯ | 25EF | large circle | circle:outlined |
| ◰ | 25F0 | white square with upper left quadrant | grid_view |
| ◱ | 25F1 | white square with lower left quadrant | grid_view |
| ◲ | 25F2 | white square with lower right quadrant | grid_view |
| ◳ | 25F3 | white square with upper right quadrant | grid_view |
| ◴ | 25F4 | white circle with upper left quadrant | pie_chart |
| ◵ | 25F5 | white circle with lower left quadrant | pie_chart |
| ◶ | 25F6 | white circle with lower right quadrant | pie_chart |
| ◷ | 25F7 | white circle with upper right quadrant | pie_chart |
| ◸ | 25F8 | upper left triangle | north_west |
| ◹ | 25F9 | upper right triangle | north_east |
| ◺ | 25FA | lower left triangle | south_west |
| ◿ | 25FF | lower right triangle | signal_cellular_0_bar |
| ⬀ | 2B00 | north east white arrow | north_east |
| ⬁ | 2B01 | north west white arrow | north_west |
| ⬂ | 2B02 | south east white arrow | south_east |
| ⬃ | 2B03 | south west white arrow | south_west |
| ⬄ | 2B04 | left right white arrow | arrow_range |
| ⬈ | 2B08 | north east black arrow | north_east |
| ⬉ | 2B09 | north west black arrow | north_west |
| ⬊ | 2B0A | south east black arrow | south_east |
| ⬋ | 2B0B | south west black arrow | south_west |
| ⬌ | 2B0C | left right black arrow | arrow_range |
| ⬍ | 2B0D | up down black arrow | swap_vert |
| ⬎ | 2B0E | rightwards arrow with tip downwards | subdirectory_arrow_right |
| ⬏ | 2B0F | rightwards arrow with tip upwards | turn_right |
| ⬐ | 2B10 | leftwards arrow with tip downwards | subdirectory_arrow_left |
| ⬑ | 2B11 | leftwards arrow with tip upwards | turn_left |
| ⬒ | 2B12 | square with top half black | splitscreen_top |
| ⬓ | 2B13 | square with bottom half black | splitscreen_bottom |
| ⬔ | 2B14 | square with upper right diagonal half black | contrast_square |
| ⬕ | 2B15 | square with lower left diagonal half black | contrast_square |
| ⬖ | 2B16 | diamond with left half black | diamond |
| ⬗ | 2B17 | diamond with right half black | diamond |
| ⬘ | 2B18 | diamond with top half black | diamond |
| ⬙ | 2B19 | diamond with bottom half black | diamond |
| ⬚ | 2B1A | dotted square | crop_free |
| ⬝ | 2B1D | black very small square | square:filled |
| ⬞ | 2B1E | white very small square | square:outlined |
| ⬟ | 2B1F | black pentagon | pentagon:filled |
| ⬠ | 2B20 | white pentagon | pentagon:outlined |
| ⬡ | 2B21 | white hexagon | hexagon:outlined |
| ⬢ | 2B22 | black hexagon | hexagon:filled |
| ⬣ | 2B23 | horizontal black hexagon | hexagon:filled |
| ⬤ | 2B24 | black large circle | circle:filled |
| ⬥ | 2B25 | black medium diamond | diamond:filled |
| ⬦ | 2B26 | white medium diamond | diamond:outlined |
| ⬧ | 2B27 | black medium lozenge | diamond:filled |
| ⬨ | 2B28 | white medium lozenge | diamond:outlined |
| ⬩ | 2B29 | black small diamond | diamond:filled |
| ⬪ | 2B2A | black small lozenge | diamond:filled |
| ⬫ | 2B2B | white small lozenge | diamond:outlined |
| ⬬ | 2B2C | black horizontal ellipse | circle:filled |
| ⬭ | 2B2D | white horizontal ellipse | circle:outlined |
| ⬮ | 2B2E | black vertical ellipse | circle:filled |
| ⬯ | 2B2F | white vertical ellipse | circle:outlined |
| ⬰ | 2B30 | left arrow with small circle | arrow_back |
| ⬱ | 2B31 | three leftwards arrows | arrow_back |
| ⬲ | 2B32 | left arrow with circled plus | arrow_back |
| ⬳ | 2B33 | long leftwards squiggle arrow | arrow_back |
| ⬴ | 2B34 | leftwards two-headed arrow with vertical stroke | keyboard_double_arrow_left |
| ⬵ | 2B35 | leftwards two-headed arrow with double vertical stroke | keyboard_double_arrow_left |
| ⬶ | 2B36 | leftwards two-headed arrow from bar | keyboard_tab_rtl |
| ⬷ | 2B37 | leftwards two-headed triple dash arrow | keyboard_double_arrow_left |
| ⬸ | 2B38 | leftwards arrow with dotted stem | arrow_back |
| ⬹ | 2B39 | leftwards arrow with tail with vertical stroke | arrow_back |
| ⬺ | 2B3A | leftwards arrow with tail with double vertical stroke | arrow_back |
| ⬻ | 2B3B | leftwards two-headed arrow with tail | keyboard_double_arrow_left |
| ⬼ | 2B3C | leftwards two-headed arrow with tail with vertical stroke | keyboard_double_arrow_left |
| ⬽ | 2B3D | leftwards two-headed arrow with tail with double vertical stroke | keyboard_double_arrow_left |
| ⬾ | 2B3E | leftwards arrow through x | arrow_back |
| ⬿ | 2B3F | wave arrow pointing directly left | arrow_back |
| ⭀ | 2B40 | equals sign above leftwards arrow | arrow_back |
| ⭁ | 2B41 | reverse tilde operator above leftwards arrow | arrow_back |
| ⭂ | 2B42 | leftwards arrow above reverse almost equal to | arrow_back |
| ⭃ | 2B43 | rightwards arrow through greater-than | arrow_forward |
| ⭄ | 2B44 | rightwards arrow through superset | arrow_forward |
| ⭅ | 2B45 | leftwards quadruple arrow | keyboard_double_arrow_left |
| ⭆ | 2B46 | rightwards quadruple arrow | keyboard_double_arrow_right |
| ⭇ | 2B47 | reverse tilde operator above rightwards arrow | arrow_forward |
| ⭈ | 2B48 | rightwards arrow above reverse almost equal to | arrow_forward |
| ⭉ | 2B49 | tilde operator above leftwards arrow | arrow_back |
| ⭊ | 2B4A | leftwards arrow above almost equal to | arrow_back |
| ⭋ | 2B4B | leftwards arrow above reverse tilde operator | arrow_back |
| ⭌ | 2B4C | rightwards arrow above reverse tilde operator | arrow_forward |
| ⭍ | 2B4D | downwards triangle-headed zigzag arrow | south |
| ⭎ | 2B4E | short slanted north arrow | north |
| ⭏ | 2B4F | short backslanted south arrow | south |
| ⭑ | 2B51 | black small star | star:filled |
| ⭒ | 2B52 | white small star | star:outlined |
| ⭓ | 2B53 | black right-pointing pentagon | pentagon:filled |
| ⭔ | 2B54 | white right-pointing pentagon | pentagon:outlined |
| ⭖ | 2B56 | heavy oval with oval inside | trip_origin |
| ⭗ | 2B57 | heavy circle with circle inside | trip_origin |
| ⭘ | 2B58 | heavy circle | circle:outlined |
| ⭙ | 2B59 | heavy circled saltire | cancel |
| ⭚ | 2B5A | slanted north arrow with hooked head | north |
| ⭛ | 2B5B | backslanted south arrow with hooked tail | south |
| ⭜ | 2B5C | slanted north arrow with horizontal tail | north |
| ⭝ | 2B5D | backslanted south arrow with horizontal tail | south |
| ⭞ | 2B5E | bent arrow pointing downwards then north east | north_east |
| ⭟ | 2B5F | short bent arrow pointing downwards then north east | north_east |
| ⭠ | 2B60 | leftwards triangle-headed arrow | arrow_back |
| ⭡ | 2B61 | upwards triangle-headed arrow | arrow_upward |
| ⭢ | 2B62 | rightwards triangle-headed arrow | arrow_forward |
| ⭣ | 2B63 | downwards triangle-headed arrow | arrow_downward |
| ⭤ | 2B64 | left right triangle-headed arrow | arrow_range |
| ⭥ | 2B65 | up down triangle-headed arrow | swap_vert |
| ⭦ | 2B66 | north west triangle-headed arrow | north_west |
| ⭧ | 2B67 | north east triangle-headed arrow | north_east |
| ⭨ | 2B68 | south east triangle-headed arrow | south_east |
| ⭩ | 2B69 | south west triangle-headed arrow | south_west |
| ⭪ | 2B6A | leftwards triangle-headed dashed arrow | arrow_back |
| ⭫ | 2B6B | upwards triangle-headed dashed arrow | arrow_upward |
| ⭬ | 2B6C | rightwards triangle-headed dashed arrow | arrow_forward |
| ⭭ | 2B6D | downwards triangle-headed dashed arrow | arrow_downward |
| ⭮ | 2B6E | clockwise triangle-headed open circle arrow | rotate_right |
| ⭯ | 2B6F | anticlockwise triangle-headed open circle arrow | rotate_left |
| ⭰ | 2B70 | leftwards triangle-headed arrow to bar | keyboard_tab_rtl |
| ⭱ | 2B71 | upwards triangle-headed arrow to bar | arrow_upward |
| ⭲ | 2B72 | rightwards triangle-headed arrow to bar | keyboard_tab |
| ⭳ | 2B73 | downwards triangle-headed arrow to bar | arrow_downward |
| ⭶ | 2B76 | north west triangle-headed arrow to bar | north_west |
| ⭷ | 2B77 | north east triangle-headed arrow to bar | north_east |
| ⭸ | 2B78 | south east triangle-headed arrow to bar | south_east |
| ⭹ | 2B79 | south west triangle-headed arrow to bar | south_west |
| ⭺ | 2B7A | leftwards triangle-headed arrow with double horizontal stroke | arrow_back |
| ⭻ | 2B7B | upwards triangle-headed arrow with double horizontal stroke | arrow_upward |
| ⭼ | 2B7C | rightwards triangle-headed arrow with double horizontal stroke | arrow_forward |
| ⭽ | 2B7D | downwards triangle-headed arrow with double horizontal stroke | arrow_downward |
| ⭾ | 2B7E | horizontal tab key | keyboard_tab |
| ⭿ | 2B7F | vertical tab key | keyboard_tab |
| ⮀ | 2B80 | leftwards triangle-headed arrow over rightwards triangle-headed arrow | swap_horiz |
| ⮁ | 2B81 | upwards triangle-headed arrow leftwards of downwards triangle-headed arrow | swap_vert |
| ⮂ | 2B82 | rightwards triangle-headed arrow over leftwards triangle-headed arrow | swap_horiz |
| ⮃ | 2B83 | downwards triangle-headed arrow leftwards of upwards triangle-headed arrow | swap_vert |
| ⮄ | 2B84 | leftwards triangle-headed paired arrows | keyboard_double_arrow_left |
| ⮅ | 2B85 | upwards triangle-headed paired arrows | keyboard_double_arrow_up |
| ⮆ | 2B86 | rightwards triangle-headed paired arrows | keyboard_double_arrow_right |
| ⮇ | 2B87 | downwards triangle-headed paired arrows | keyboard_double_arrow_down |
| ⮈ | 2B88 | leftwards black circled white arrow | arrow_circle_left |
| ⮉ | 2B89 | upwards black circled white arrow | arrow_circle_up |
| ⮊ | 2B8A | rightwards black circled white arrow | arrow_circle_right |
| ⮋ | 2B8B | downwards black circled white arrow | arrow_circle_down |
| ⮌ | 2B8C | anticlockwise triangle-headed right u-shaped arrow | rotate_left |
| ⮍ | 2B8D | anticlockwise triangle-headed bottom u-shaped arrow | rotate_left |
| ⮎ | 2B8E | anticlockwise triangle-headed left u-shaped arrow | rotate_left |
| ⮏ | 2B8F | anticlockwise triangle-headed top u-shaped arrow | rotate_left |
| ⮐ | 2B90 | return left | keyboard_return |
| ⮑ | 2B91 | return right | keyboard_return |
| ⮒ | 2B92 | newline left | keyboard_return |
| ⮓ | 2B93 | newline right | keyboard_return |
| ⮔ | 2B94 | four corner arrows circling anticlockwise | sync |
| ⮕ | 2B95 | rightwards black arrow | arrow_forward |
| ⮗ | 2B97 | symbol for type a electronics | bolt |
| ⮘ | 2B98 | three-d top-lighted leftwards equilateral arrowhead | arrow_left:filled |
| ⮙ | 2B99 | three-d right-lighted upwards equilateral arrowhead | arrow_drop_up:filled |
| ⮚ | 2B9A | three-d top-lighted rightwards equilateral arrowhead | arrow_right:filled |
| ⮛ | 2B9B | three-d left-lighted downwards equilateral arrowhead | arrow_drop_down:filled |
| ⮜ | 2B9C | black leftwards equilateral arrowhead | arrow_left:filled |
| ⮝ | 2B9D | black upwards equilateral arrowhead | arrow_drop_up:filled |
| ⮞ | 2B9E | black rightwards equilateral arrowhead | arrow_right:filled |
| ⮟ | 2B9F | black downwards equilateral arrowhead | arrow_drop_down:filled |
| ⮠ | 2BA0 | downwards triangle-headed arrow with long tip leftwards | subdirectory_arrow_left |
| ⮡ | 2BA1 | downwards triangle-headed arrow with long tip rightwards | subdirectory_arrow_right |
| ⮢ | 2BA2 | upwards triangle-headed arrow with long tip leftwards | turn_left |
| ⮣ | 2BA3 | upwards triangle-headed arrow with long tip rightwards | turn_right |
| ⮤ | 2BA4 | leftwards triangle-headed arrow with long tip upwards | turn_left |
| ⮥ | 2BA5 | rightwards triangle-headed arrow with long tip upwards | turn_right |
| ⮦ | 2BA6 | leftwards triangle-headed arrow with long tip downwards | subdirectory_arrow_left |
| ⮧ | 2BA7 | rightwards triangle-headed arrow with long tip downwards | subdirectory_arrow_right |
| ⮨ | 2BA8 | black curved downwards and leftwards arrow | south_west |
| ⮩ | 2BA9 | black curved downwards and rightwards arrow | south_east |
| ⮪ | 2BAA | black curved upwards and leftwards arrow | north_west |
| ⮫ | 2BAB | black curved upwards and rightwards arrow | north_east |
| ⮬ | 2BAC | black curved leftwards and upwards arrow | north_west |
| ⮭ | 2BAD | black curved rightwards and upwards arrow | north_east |
| ⮮ | 2BAE | black curved leftwards and downwards arrow | south_west |
| ⮯ | 2BAF | black curved rightwards and downwards arrow | south_east |
| ⮰ | 2BB0 | ribbon arrow down left | south_west |
| ⮱ | 2BB1 | ribbon arrow down right | south_east |
| ⮲ | 2BB2 | ribbon arrow up left | north_west |
| ⮳ | 2BB3 | ribbon arrow up right | north_east |
| ⮴ | 2BB4 | ribbon arrow left up | north_west |
| ⮵ | 2BB5 | ribbon arrow right up | north_east |
| ⮶ | 2BB6 | ribbon arrow left down | south_west |
| ⮷ | 2BB7 | ribbon arrow right down | south_east |
| ⮸ | 2BB8 | upwards white arrow from bar with horizontal bar | keyboard_capslock |
| ⮹ | 2BB9 | up arrowhead in a rectangle box | keyboard_capslock |
| ⮺ | 2BBA | overlapping white squares | content_copy |
| ⮻ | 2BBB | overlapping white and black squares | content_copy |
| ⮼ | 2BBC | overlapping black squares | content_copy:filled |
| ⮽ | 2BBD | ballot box with light x | disabled_by_default |
| ⮾ | 2BBE | circled x | cancel |
| ⮿ | 2BBF | circled bold x | cancel |
| ⯀ | 2BC0 | black square centred | square:filled |
| ⯁ | 2BC1 | black diamond centred | diamond:filled |
| ⯂ | 2BC2 | turned black pentagon | pentagon:filled |
| ⯃ | 2BC3 | horizontal black octagon | hexagon:filled |
| ⯄ | 2BC4 | black octagon | hexagon:filled |
| ⯅ | 2BC5 | black medium up-pointing triangle centred | arrow_drop_up:filled |
| ⯆ | 2BC6 | black medium down-pointing triangle centred | arrow_drop_down:filled |
| ⯇ | 2BC7 | black medium left-pointing triangle centred | arrow_left:filled |
| ⯈ | 2BC8 | black medium right-pointing triangle centred | arrow_right:filled |
| ⯉ | 2BC9 | neptune form two | planet |
| ⯊ | 2BCA | top half black circle | contrast |
| ⯋ | 2BCB | bottom half black circle | contrast |
| ⯌ | 2BCC | light four pointed black cusp | star_shine |
| ⯍ | 2BCD | rotated light four pointed black cusp | star_shine |
| ⯎ | 2BCE | white four pointed cusp | star:outlined |
| ⯏ | 2BCF | rotated white four pointed cusp | star:outlined |
| ⯐ | 2BD0 | square position indicator | crop_free |
| ⯑ | 2BD1 | uncertainty sign | question_mark |
| ⯒ | 2BD2 | group mark | workspaces |
| ⯓ | 2BD3 | pluto form two | planet |
| ⯔ | 2BD4 | pluto form three | planet |
| ⯕ | 2BD5 | pluto form four | planet |
| ⯖ | 2BD6 | pluto form five | planet |
| ⯗ | 2BD7 | transpluto | public |
| ⯘ | 2BD8 | proserpina | public |
| ⯙ | 2BD9 | astraea | public |
| ⯚ | 2BDA | hygiea | public |
| ⯛ | 2BDB | pholus | public |
| ⯜ | 2BDC | nessus | public |
| ⯝ | 2BDD | white moon selena | dark_mode:outlined |
| ⯞ | 2BDE | black diamond on cross | diamond:filled |
| ⯟ | 2BDF | true light moon arta | dark_mode:filled |
| ⯠ | 2BE0 | cupido | public |
| ⯡ | 2BE1 | hades | public |
| ⯢ | 2BE2 | zeus | public |
| ⯣ | 2BE3 | kronos | public |
| ⯤ | 2BE4 | apollon | public |
| ⯥ | 2BE5 | admetos | public |
| ⯦ | 2BE6 | vulcanus | public |
| ⯧ | 2BE7 | poseidon | public |
| ⯨ | 2BE8 | left half black star | star_half |
| ⯩ | 2BE9 | right half black star | star_half |
| ⯪ | 2BEA | star with left half black | star_half |
| ⯫ | 2BEB | star with right half black | star_half |
| ⯬ | 2BEC | leftwards two-headed arrow with triangle arrowheads | keyboard_double_arrow_left |
| ⯭ | 2BED | upwards two-headed arrow with triangle arrowheads | keyboard_double_arrow_up |
| ⯮ | 2BEE | rightwards two-headed arrow with triangle arrowheads | keyboard_double_arrow_right |
| ⯯ | 2BEF | downwards two-headed arrow with triangle arrowheads | keyboard_double_arrow_down |
| ⯰ | 2BF0 | eris form one | public |
| ⯱ | 2BF1 | eris form two | public |
| ⯲ | 2BF2 | sedna | public |
| ⯳ | 2BF3 | russian astrological symbol vigintile | public |
| ⯴ | 2BF4 | russian astrological symbol novile | public |
| ⯵ | 2BF5 | russian astrological symbol quintile | public |
| ⯶ | 2BF6 | russian astrological symbol binovile | public |
| ⯷ | 2BF7 | russian astrological symbol sentagon | public |
| ⯸ | 2BF8 | russian astrological symbol tredecile | public |
| ⯹ | 2BF9 | equals sign with infinity below | all_inclusive |
| ⯺ | 2BFA | united symbol | workspaces |
| ⯻ | 2BFB | separated symbol | workspaces |
| ⯼ | 2BFC | doubled symbol | workspaces |
| ⯽ | 2BFD | passed symbol | workspaces |
| ⯾ | 2BFE | reversed right angle | rounded_corner |
| ⯿ | 2BFF | hellschreiber pause symbol | pause |
| 🌢 | 1F322 | black droplet | water_drop:filled |
| 🌣 | 1F323 | white sun | wb_sunny:outlined |
| 🎔 | 1F394 | heart with tip on the left | favorite |
| 🎕 | 1F395 | bouquet of flowers | local_florist |
| 🎘 | 1F398 | musical keyboard with jacks | piano |
| 🎜 | 1F39C | beamed ascending musical notes | music_note |
| 🎝 | 1F39D | beamed descending musical notes | music_note |
| 🏱 | 1F3F1 | white pennant | flag:outlined |
| 🏲 | 1F3F2 | black pennant | flag:filled |
| 🏶 | 1F3F6 | black rosette | local_florist:filled |
| 📾 | 1F4FE | portable stereo | speaker |
| 🔾 | 1F53E | lower right shadowed white circle | circle:outlined |
| 🔿 | 1F53F | upper right shadowed white circle | circle:outlined |
| 🕀 | 1F540 | circled cross pommee | add_circle |
| 🕁 | 1F541 | cross pommee with half-circle below | add |
| 🕂 | 1F542 | cross pommee | add |
| 🕃 | 1F543 | notched left semicircle with three dots | more_horiz |
| 🕄 | 1F544 | notched right semicircle with three dots | more_horiz |
| 🕅 | 1F545 | symbol for marks chapter | menu_book |
| 🕆 | 1F546 | white latin cross | add:outlined |
| 🕇 | 1F547 | heavy latin cross | add:filled |
| 🕈 | 1F548 | celtic cross | add |
| 🕏 | 1F54F | bowl of hygieia | local_pharmacy |
| 🕨 | 1F568 | right speaker | volume_mute |
| 🕩 | 1F569 | right speaker with one sound wave | volume_down |
| 🕪 | 1F56A | right speaker with three sound waves | volume_up |
| 🕫 | 1F56B | bullhorn | campaign |
| 🕬 | 1F56C | bullhorn with sound waves | campaign |
| 🕭 | 1F56D | ringing bell | notifications_active |
| 🕮 | 1F56E | book | menu_book |
| 🕱 | 1F571 | black skull and crossbones | skull:filled |
| 🕲 | 1F572 | no piracy | block |
| 🕻 | 1F57B | left hand telephone receiver | phone |
| 🕼 | 1F57C | telephone receiver with page | phone |
| 🕽 | 1F57D | right hand telephone receiver | phone |
| 🕾 | 1F57E | white touchtone telephone | phone:outlined |
| 🕿 | 1F57F | black touchtone telephone | phone:filled |
| 🖀 | 1F580 | telephone on top of modem | phone |
| 🖁 | 1F581 | clamshell mobile phone | smartphone |
| 🖂 | 1F582 | back of envelope | mail |
| 🖃 | 1F583 | stamped envelope | mail |
| 🖄 | 1F584 | envelope with lightning | mark_email_unread |
| 🖅 | 1F585 | flying envelope | forward_to_inbox |
| 🖆 | 1F586 | pen over stamped envelope | drafts |
| 🖈 | 1F588 | black pushpin | push_pin:filled |
| 🖉 | 1F589 | lower left pencil | edit |
| 🖎 | 1F58E | left writing hand | edit |
| 🖏 | 1F58F | turned ok hand sign | thumb_up |
| 🖑 | 1F591 | reversed raised hand with fingers splayed | back_hand |
| 🖒 | 1F592 | reversed thumbs up sign | thumb_up |
| 🖓 | 1F593 | reversed thumbs down sign | thumb_down |
| 🖔 | 1F594 | reversed victory hand | back_hand |
| 🖗 | 1F597 | white down pointing left hand index | arrow_downward:outlined |
| 🖘 | 1F598 | sideways white left pointing index | arrow_back:outlined |
| 🖙 | 1F599 | sideways white right pointing index | arrow_forward:outlined |
| 🖚 | 1F59A | sideways black left pointing index | arrow_back:filled |
| 🖛 | 1F59B | sideways black right pointing index | arrow_forward:filled |
| 🖜 | 1F59C | black left pointing backhand index | arrow_back:filled |
| 🖝 | 1F59D | black right pointing backhand index | arrow_forward:filled |
| 🖞 | 1F59E | sideways white up pointing index | arrow_upward:outlined |
| 🖟 | 1F59F | sideways white down pointing index | arrow_downward:outlined |
| 🖠 | 1F5A0 | sideways black up pointing index | arrow_upward:filled |
| 🖡 | 1F5A1 | sideways black down pointing index | arrow_downward:filled |
| 🖢 | 1F5A2 | black up pointing backhand index | arrow_upward:filled |
| 🖣 | 1F5A3 | black down pointing backhand index | arrow_downward:filled |
| 🖦 | 1F5A6 | keyboard and mouse | keyboard |
| 🖧 | 1F5A7 | three networked computers | lan |
| 🖩 | 1F5A9 | pocket calculator | calculate |
| 🖪 | 1F5AA | black hard shell floppy disk | save:filled |
| 🖫 | 1F5AB | white hard shell floppy disk | save:outlined |
| 🖬 | 1F5AC | soft shell floppy disk | save |
| 🖭 | 1F5AD | tape cartridge | album |
| 🖮 | 1F5AE | wired keyboard | keyboard |
| 🖯 | 1F5AF | one button mouse | mouse |
| 🖰 | 1F5B0 | two button mouse | mouse |
| 🖳 | 1F5B3 | old personal computer | computer |
| 🖴 | 1F5B4 | hard disk | hard_drive |
| 🖵 | 1F5B5 | screen | desktop_windows |
| 🖶 | 1F5B6 | printer icon | print |
| 🖷 | 1F5B7 | fax icon | fax |
| 🖸 | 1F5B8 | optical disc icon | album |
| 🖹 | 1F5B9 | document with text | article |
| 🖺 | 1F5BA | document with text and picture | article |
| 🖻 | 1F5BB | document with picture | image |
| 🖽 | 1F5BD | frame with tiles | grid_view |
| 🖾 | 1F5BE | frame with an x | broken_image |
| 🖿 | 1F5BF | black folder | folder:filled |
| 🗀 | 1F5C0 | folder | folder:outlined |
| 🗁 | 1F5C1 | open folder | folder_open |
| 🗅 | 1F5C5 | empty note | sticky_note_2:outlined |
| 🗆 | 1F5C6 | empty note page | sticky_note_2:outlined |
| 🗇 | 1F5C7 | empty note pad | sticky_note_2:outlined |
| 🗈 | 1F5C8 | note | sticky_note_2 |
| 🗉 | 1F5C9 | note page | sticky_note_2 |
| 🗊 | 1F5CA | note pad | sticky_note_2 |
| 🗋 | 1F5CB | empty document | description:outlined |
| 🗌 | 1F5CC | empty page | description:outlined |
| 🗍 | 1F5CD | empty pages | description:outlined |
| 🗎 | 1F5CE | document | description |
| 🗏 | 1F5CF | page | description |
| 🗐 | 1F5D0 | pages | description |
| 🗔 | 1F5D4 | desktop window | web_asset |
| 🗕 | 1F5D5 | minimize | minimize |
| 🗖 | 1F5D6 | maximize | crop_square |
| 🗗 | 1F5D7 | overlap | filter_none |
| 🗘 | 1F5D8 | clockwise right and left semicircle arrows | sync |
| 🗙 | 1F5D9 | cancellation x | close |
| 🗚 | 1F5DA | increase font size symbol | text_increase |
| 🗛 | 1F5DB | decrease font size symbol | text_decrease |
| 🗟 | 1F5DF | page with circled text | find_in_page |
| 🗠 | 1F5E0 | stock chart | candlestick_chart |
| 🗢 | 1F5E2 | lips | sentiment_satisfied |
| 🗤 | 1F5E4 | three rays above | north |
| 🗥 | 1F5E5 | three rays below | south |
| 🗦 | 1F5E6 | three rays left | west |
| 🗧 | 1F5E7 | three rays right | east |
| 🗩 | 1F5E9 | right speech bubble | chat_bubble |
| 🗪 | 1F5EA | two speech bubbles | forum |
| 🗫 | 1F5EB | three speech bubbles | forum |
| 🗬 | 1F5EC | left thought bubble | chat_bubble |
| 🗭 | 1F5ED | right thought bubble | chat_bubble |
| 🗮 | 1F5EE | left anger bubble | chat_bubble |
| 🗰 | 1F5F0 | mood bubble | mood |
| 🗱 | 1F5F1 | lightning mood bubble | bolt |
| 🗲 | 1F5F2 | lightning mood | bolt |
| 🗴 | 1F5F4 | ballot script x | close |
| 🗵 | 1F5F5 | ballot box with script x | disabled_by_default:outlined |
| 🗶 | 1F5F6 | ballot bold script x | close |
| 🗷 | 1F5F7 | ballot box with bold script x | disabled_by_default:filled |
| 🗸 | 1F5F8 | light check mark | check |
| 🗹 | 1F5F9 | ballot box with bold check | check_box:filled |
| 🙐 | 1F650 | north west pointing leaf | eco |
| 🙑 | 1F651 | south west pointing leaf | eco |
| 🙒 | 1F652 | north east pointing leaf | eco |
| 🙓 | 1F653 | south east pointing leaf | eco |
| 🙔 | 1F654 | turned north west pointing leaf | eco |
| 🙕 | 1F655 | turned south west pointing leaf | eco |
| 🙖 | 1F656 | turned north east pointing leaf | eco |
| 🙗 | 1F657 | turned south east pointing leaf | eco |
| 🙘 | 1F658 | north west pointing vine leaf | eco |
| 🙙 | 1F659 | south west pointing vine leaf | eco |
| 🙚 | 1F65A | north east pointing vine leaf | eco |
| 🙛 | 1F65B | south east pointing vine leaf | eco |
| 🙜 | 1F65C | heavy north west pointing vine leaf | eco:filled |
| 🙝 | 1F65D | heavy south west pointing vine leaf | eco:filled |
| 🙞 | 1F65E | heavy north east pointing vine leaf | eco:filled |
| 🙟 | 1F65F | heavy south east pointing vine leaf | eco:filled |
| 🙠 | 1F660 | north west pointing bud | local_florist |
| 🙡 | 1F661 | south west pointing bud | local_florist |
| 🙢 | 1F662 | north east pointing bud | local_florist |
| 🙣 | 1F663 | south east pointing bud | local_florist |
| 🙤 | 1F664 | heavy north west pointing bud | local_florist:filled |
| 🙥 | 1F665 | heavy south west pointing bud | local_florist:filled |
| 🙦 | 1F666 | heavy north east pointing bud | local_florist:filled |
| 🙧 | 1F667 | heavy south east pointing bud | local_florist:filled |
| 🙨 | 1F668 | hollow quilt square ornament | grid_on |
| 🙩 | 1F669 | hollow quilt square ornament in black square | grid_on:filled |
| 🙪 | 1F66A | solid quilt square ornament | grid_on |
| 🙫 | 1F66B | solid quilt square ornament in black square | grid_on:filled |
| 🙬 | 1F66C | leftwards rocket | rocket_launch |
| 🙭 | 1F66D | upwards rocket | rocket_launch |
| 🙮 | 1F66E | rightwards rocket | rocket_launch |
| 🙯 | 1F66F | downwards rocket | rocket_launch |
| 🙰 | 1F670 | script ligature et ornament | sort_by_alpha |
| 🙱 | 1F671 | heavy script ligature et ornament | sort_by_alpha |
| 🙲 | 1F672 | ligature open et ornament | sort_by_alpha |
| 🙳 | 1F673 | heavy ligature open et ornament | sort_by_alpha |
| 🙴 | 1F674 | heavy ampersand ornament | sort_by_alpha |
| 🙵 | 1F675 | swash ampersand ornament | sort_by_alpha |
| 🙶 | 1F676 | sans-serif heavy double turned comma quotation mark ornament | format_quote |
| 🙷 | 1F677 | sans-serif heavy double comma quotation mark ornament | format_quote |
| 🙸 | 1F678 | sans-serif heavy low double comma quotation mark ornament | format_quote |
| 🙹 | 1F679 | heavy interrobang ornament | priority_high |
| 🙺 | 1F67A | sans-serif interrobang ornament | priority_high |
| 🙻 | 1F67B | heavy sans-serif interrobang ornament | priority_high |
| 🙼 | 1F67C | very heavy solidus | horizontal_rule |
| 🙽 | 1F67D | very heavy reverse solidus | horizontal_rule |
| 🙾 | 1F67E | checker board | grid_on:outlined |
| 🙿 | 1F67F | reverse checker board | grid_on:filled |
| 🛆 | 1F6C6 | triangle with rounded corners | change_history |
| 🛇 | 1F6C7 | prohibited sign | block |
| 🛈 | 1F6C8 | circled information source | info |
| 🛉 | 1F6C9 | boys symbol | man |
| 🛊 | 1F6CA | girls symbol | woman |
| 🛓 | 1F6D3 | stupa | temple_buddhist |
| 🛔 | 1F6D4 | pagoda | temple_buddhist |
| 🛦 | 1F6E6 | up-pointing military airplane | flight |
| 🛧 | 1F6E7 | up-pointing airplane | flight |
| 🛨 | 1F6E8 | up-pointing small airplane | flight |
| 🛪 | 1F6EA | northeast-pointing airplane | flight |
| 🛱 | 1F6F1 | oncoming fire engine | fire_truck |
| 🛲 | 1F6F2 | diesel locomotive | train |
| 🜀 | 1F700 | alchemical symbol for quintessence | stars |
| 🜁 | 1F701 | alchemical symbol for air | air |
| 🜂 | 1F702 | alchemical symbol for fire | local_fire_department |
| 🜃 | 1F703 | alchemical symbol for earth | landscape |
| 🜄 | 1F704 | alchemical symbol for water | water_drop |
| 🜅 | 1F705 | alchemical symbol for aquafortis | water_drop |
| 🜆 | 1F706 | alchemical symbol for aqua regia | water_drop |
| 🜇 | 1F707 | alchemical symbol for aqua regia-2 | water_drop |
| 🜈 | 1F708 | alchemical symbol for aqua vitae | water_drop |
| 🜉 | 1F709 | alchemical symbol for aqua vitae-2 | water_drop |
| 🜊 | 1F70A | alchemical symbol for vinegar | water_drop |
| 🜋 | 1F70B | alchemical symbol for vinegar-2 | water_drop |
| 🜌 | 1F70C | alchemical symbol for vinegar-3 | water_drop |
| 🜍 | 1F70D | alchemical symbol for sulfur | local_fire_department |
| 🜎 | 1F70E | alchemical symbol for philosophers sulfur | local_fire_department |
| 🜏 | 1F70F | alchemical symbol for black sulfur | local_fire_department |
| 🜐 | 1F710 | alchemical symbol for mercury sublimate | science |
| 🜑 | 1F711 | alchemical symbol for mercury sublimate-2 | science |
| 🜒 | 1F712 | alchemical symbol for mercury sublimate-3 | science |
| 🜓 | 1F713 | alchemical symbol for cinnabar | science |
| 🜔 | 1F714 | alchemical symbol for salt | grain |
| 🜕 | 1F715 | alchemical symbol for nitre | grain |
| 🜖 | 1F716 | alchemical symbol for vitriol | science |
| 🜗 | 1F717 | alchemical symbol for vitriol-2 | science |
| 🜘 | 1F718 | alchemical symbol for rock salt | grain |
| 🜙 | 1F719 | alchemical symbol for rock salt-2 | grain |
| 🜚 | 1F71A | alchemical symbol for gold | paid |
| 🜛 | 1F71B | alchemical symbol for silver | paid |
| 🜜 | 1F71C | alchemical symbol for iron ore | construction |
| 🜝 | 1F71D | alchemical symbol for iron ore-2 | construction |
| 🜞 | 1F71E | alchemical symbol for crocus of iron | construction |
| 🜟 | 1F71F | alchemical symbol for regulus of iron | construction |
| 🜠 | 1F720 | alchemical symbol for copper ore | science |
| 🜡 | 1F721 | alchemical symbol for iron-copper ore | construction |
| 🜢 | 1F722 | alchemical symbol for sublimate of copper | science |
| 🜣 | 1F723 | alchemical symbol for crocus of copper | science |
| 🜤 | 1F724 | alchemical symbol for crocus of copper-2 | science |
| 🜥 | 1F725 | alchemical symbol for copper antimoniate | science |
| 🜦 | 1F726 | alchemical symbol for salt of copper antimoniate | science |
| 🜧 | 1F727 | alchemical symbol for sublimate of salt of copper | science |
| 🜨 | 1F728 | alchemical symbol for verdigris | science |
| 🜩 | 1F729 | alchemical symbol for tin ore | terrain |
| 🜪 | 1F72A | alchemical symbol for lead ore | terrain |
| 🜫 | 1F72B | alchemical symbol for antimony ore | terrain |
| 🜬 | 1F72C | alchemical symbol for sublimate of antimony | science |
| 🜭 | 1F72D | alchemical symbol for salt of antimony | grain |
| 🜮 | 1F72E | alchemical symbol for sublimate of salt of antimony | grain |
| 🜯 | 1F72F | alchemical symbol for vinegar of antimony | water_drop |
| 🜰 | 1F730 | alchemical symbol for regulus of antimony | science |
| 🜱 | 1F731 | alchemical symbol for regulus of antimony-2 | science |
| 🜲 | 1F732 | alchemical symbol for regulus | science |
| 🜳 | 1F733 | alchemical symbol for regulus-2 | science |
| 🜴 | 1F734 | alchemical symbol for regulus-3 | science |
| 🜵 | 1F735 | alchemical symbol for regulus-4 | science |
| 🜶 | 1F736 | alchemical symbol for alkali | science |
| 🜷 | 1F737 | alchemical symbol for alkali-2 | science |
| 🜸 | 1F738 | alchemical symbol for marcasite | science |
| 🜹 | 1F739 | alchemical symbol for sal-ammoniac | science |
| 🜺 | 1F73A | alchemical symbol for arsenic | science |
| 🜻 | 1F73B | alchemical symbol for realgar | science |
| 🜼 | 1F73C | alchemical symbol for realgar-2 | science |
| 🜽 | 1F73D | alchemical symbol for auripigment | science |
| 🜾 | 1F73E | alchemical symbol for bismuth ore | terrain |
| 🜿 | 1F73F | alchemical symbol for tartar | science |
| 🝀 | 1F740 | alchemical symbol for tartar-2 | science |
| 🝁 | 1F741 | alchemical symbol for quick lime | science |
| 🝂 | 1F742 | alchemical symbol for borax | science |
| 🝃 | 1F743 | alchemical symbol for borax-2 | science |
| 🝄 | 1F744 | alchemical symbol for borax-3 | science |
| 🝅 | 1F745 | alchemical symbol for alum | science |
| 🝆 | 1F746 | alchemical symbol for oil | water_drop |
| 🝇 | 1F747 | alchemical symbol for spirit | air |
| 🝈 | 1F748 | alchemical symbol for tincture | water_drop |
| 🝉 | 1F749 | alchemical symbol for gum | science |
| 🝊 | 1F74A | alchemical symbol for wax | water_drop |
| 🝋 | 1F74B | alchemical symbol for powder | grain |
| 🝌 | 1F74C | alchemical symbol for calx | science |
| 🝍 | 1F74D | alchemical symbol for tutty | science |
| 🝎 | 1F74E | alchemical symbol for caput mortuum | science |
| 🝏 | 1F74F | alchemical symbol for scepter of jove | call_split |
| 🝐 | 1F750 | alchemical symbol for caduceus | local_hospital |
| 🝑 | 1F751 | alchemical symbol for trident | call_split |
| 🝒 | 1F752 | alchemical symbol for starred trident | call_split |
| 🝓 | 1F753 | alchemical symbol for lodestone | science |
| 🝔 | 1F754 | alchemical symbol for soap | water_drop |
| 🝕 | 1F755 | alchemical symbol for urine | water_drop |
| 🝖 | 1F756 | alchemical symbol for horse dung | science |
| 🝗 | 1F757 | alchemical symbol for ashes | grain |
| 🝘 | 1F758 | alchemical symbol for pot ashes | grain |
| 🝙 | 1F759 | alchemical symbol for brick | view_module |
| 🝚 | 1F75A | alchemical symbol for powdered brick | grain |
| 🝛 | 1F75B | alchemical symbol for amalgam | science |
| 🝜 | 1F75C | alchemical symbol for stratum super stratum | layers |
| 🝝 | 1F75D | alchemical symbol for stratum super stratum-2 | layers |
| 🝞 | 1F75E | alchemical symbol for sublimation | science |
| 🝟 | 1F75F | alchemical symbol for precipitate | science |
| 🝠 | 1F760 | alchemical symbol for distill | science |
| 🝡 | 1F761 | alchemical symbol for dissolve | water_drop |
| 🝢 | 1F762 | alchemical symbol for dissolve-2 | water_drop |
| 🝣 | 1F763 | alchemical symbol for purify | science |
| 🝤 | 1F764 | alchemical symbol for putrefaction | science |
| 🝥 | 1F765 | alchemical symbol for crucible | science |
| 🝦 | 1F766 | alchemical symbol for crucible-2 | science |
| 🝧 | 1F767 | alchemical symbol for crucible-3 | science |
| 🝨 | 1F768 | alchemical symbol for crucible-4 | science |
| 🝩 | 1F769 | alchemical symbol for crucible-5 | science |
| 🝪 | 1F76A | alchemical symbol for alembic | science |
| 🝫 | 1F76B | alchemical symbol for bath of mary | hot_tub |
| 🝬 | 1F76C | alchemical symbol for bath of vapours | hot_tub |
| 🝭 | 1F76D | alchemical symbol for retort | science |
| 🝮 | 1F76E | alchemical symbol for hour | schedule |
| 🝯 | 1F76F | alchemical symbol for night | dark_mode |
| 🝰 | 1F770 | alchemical symbol for day-night | dark_mode |
| 🝱 | 1F771 | alchemical symbol for month | calendar_month |
| 🝲 | 1F772 | alchemical symbol for half dram | looks_two |
| 🝳 | 1F773 | alchemical symbol for half ounce | looks_two |
| 🝴 | 1F774 | lot of fortune | stars |
| 🝵 | 1F775 | occultation | brightness_3 |
| 🝶 | 1F776 | lunar eclipse | brightness_3 |
| 🝻 | 1F77B | haumea | public |
| 🝼 | 1F77C | makemake | public |
| 🝽 | 1F77D | gonggong | public |
| 🝾 | 1F77E | quaoar | public |
| 🝿 | 1F77F | orcus | public |
| 🞀 | 1F780 | black left-pointing isosceles right triangle | arrow_left:filled |
| 🞁 | 1F781 | black up-pointing isosceles right triangle | arrow_drop_up:filled |
| 🞂 | 1F782 | black right-pointing isosceles right triangle | arrow_right:filled |
| 🞃 | 1F783 | black down-pointing isosceles right triangle | arrow_drop_down:filled |
| 🞄 | 1F784 | black slightly small circle | circle:filled |
| 🞅 | 1F785 | medium bold white circle | circle:outlined |
| 🞆 | 1F786 | bold white circle | circle:outlined |
| 🞇 | 1F787 | heavy white circle | circle:outlined |
| 🞈 | 1F788 | very heavy white circle | circle:outlined |
| 🞉 | 1F789 | extremely heavy white circle | circle:outlined |
| 🞊 | 1F78A | white circle containing black small circle | circle |
| 🞋 | 1F78B | round target | adjust |
| 🞌 | 1F78C | black tiny square | crop_square:filled |
| 🞍 | 1F78D | black slightly small square | crop_square:filled |
| 🞎 | 1F78E | light white square | crop_square:outlined |
| 🞏 | 1F78F | medium white square | crop_square:outlined |
| 🞐 | 1F790 | bold white square | crop_square:outlined |
| 🞑 | 1F791 | heavy white square | crop_square:outlined |
| 🞒 | 1F792 | very heavy white square | crop_square:outlined |
| 🞓 | 1F793 | extremely heavy white square | crop_square:outlined |
| 🞔 | 1F794 | white square containing black very small square | crop_square |
| 🞕 | 1F795 | white square containing black medium square | crop_square |
| 🞖 | 1F796 | square target | center_focus_strong |
| 🞗 | 1F797 | black tiny diamond | diamond:filled |
| 🞘 | 1F798 | black very small diamond | diamond:filled |
| 🞙 | 1F799 | black medium small diamond | diamond:filled |
| 🞚 | 1F79A | white diamond containing black very small diamond | diamond |
| 🞛 | 1F79B | white diamond containing black medium diamond | diamond |
| 🞜 | 1F79C | diamond target | adjust |
| 🞝 | 1F79D | black tiny lozenge | diamond:filled |
| 🞞 | 1F79E | black very small lozenge | diamond:filled |
| 🞟 | 1F79F | black medium small lozenge | diamond:filled |
| 🞠 | 1F7A0 | white lozenge containing black small lozenge | diamond |
| 🞡 | 1F7A1 | thin greek cross | add |
| 🞢 | 1F7A2 | light greek cross | add |
| 🞣 | 1F7A3 | medium greek cross | add |
| 🞤 | 1F7A4 | bold greek cross | add |
| 🞥 | 1F7A5 | very bold greek cross | add |
| 🞦 | 1F7A6 | very heavy greek cross | add |
| 🞧 | 1F7A7 | extremely heavy greek cross | add |
| 🞨 | 1F7A8 | thin saltire | close |
| 🞩 | 1F7A9 | light saltire | close |
| 🞪 | 1F7AA | medium saltire | close |
| 🞫 | 1F7AB | bold saltire | close |
| 🞬 | 1F7AC | heavy saltire | close |
| 🞭 | 1F7AD | very heavy saltire | close |
| 🞮 | 1F7AE | extremely heavy saltire | close |
| 🞯 | 1F7AF | light five spoked asterisk | star_rate |
| 🞰 | 1F7B0 | medium five spoked asterisk | star_rate |
| 🞱 | 1F7B1 | bold five spoked asterisk | star_rate |
| 🞲 | 1F7B2 | heavy five spoked asterisk | star_rate |
| 🞳 | 1F7B3 | very heavy five spoked asterisk | star_rate |
| 🞴 | 1F7B4 | extremely heavy five spoked asterisk | star_rate |
| 🞵 | 1F7B5 | light six spoked asterisk | emergency |
| 🞶 | 1F7B6 | medium six spoked asterisk | emergency |
| 🞷 | 1F7B7 | bold six spoked asterisk | emergency |
| 🞸 | 1F7B8 | heavy six spoked asterisk | emergency |
| 🞹 | 1F7B9 | very heavy six spoked asterisk | emergency |
| 🞺 | 1F7BA | extremely heavy six spoked asterisk | emergency |
| 🞻 | 1F7BB | light eight spoked asterisk | flare |
| 🞼 | 1F7BC | medium eight spoked asterisk | flare |
| 🞽 | 1F7BD | bold eight spoked asterisk | flare |
| 🞾 | 1F7BE | heavy eight spoked asterisk | flare |
| 🞿 | 1F7BF | very heavy eight spoked asterisk | flare |
| 🟀 | 1F7C0 | light three pointed black star | star:filled |
| 🟁 | 1F7C1 | medium three pointed black star | star:filled |
| 🟂 | 1F7C2 | three pointed black star | star:filled |
| 🟃 | 1F7C3 | medium three pointed pinwheel star | star |
| 🟄 | 1F7C4 | light four pointed black star | star:filled |
| 🟅 | 1F7C5 | medium four pointed black star | star:filled |
| 🟆 | 1F7C6 | four pointed black star | star:filled |
| 🟇 | 1F7C7 | medium four pointed pinwheel star | star |
| 🟈 | 1F7C8 | reverse light four pointed pinwheel star | star |
| 🟉 | 1F7C9 | light five pointed black star | star:filled |
| 🟊 | 1F7CA | heavy five pointed black star | star:filled |
| 🟋 | 1F7CB | medium six pointed black star | star:filled |
| 🟌 | 1F7CC | heavy six pointed black star | star:filled |
| 🟍 | 1F7CD | six pointed pinwheel star | star |
| 🟎 | 1F7CE | medium eight pointed black star | star:filled |
| 🟏 | 1F7CF | heavy eight pointed black star | star:filled |
| 🟐 | 1F7D0 | very heavy eight pointed black star | star:filled |
| 🟑 | 1F7D1 | heavy eight pointed pinwheel star | star |
| 🟒 | 1F7D2 | light twelve pointed black star | star:filled |
| 🟓 | 1F7D3 | heavy twelve pointed black star | star:filled |
| 🟔 | 1F7D4 | heavy twelve pointed pinwheel star | star |
| 🟕 | 1F7D5 | circled triangle | change_history:outlined |
| 🟖 | 1F7D6 | negative circled triangle | change_history:filled |
| 🟗 | 1F7D7 | circled square | check_box_outline_blank |
| 🟘 | 1F7D8 | negative circled square | check_box:filled |
| 🟙 | 1F7D9 | nine pointed white star | star:outlined |
| 🠀 | 1F800 | leftwards arrow with small triangle arrowhead | arrow_left |
| 🠁 | 1F801 | upwards arrow with small triangle arrowhead | arrow_drop_up |
| 🠂 | 1F802 | rightwards arrow with small triangle arrowhead | arrow_right |
| 🠃 | 1F803 | downwards arrow with small triangle arrowhead | arrow_drop_down |
| 🠄 | 1F804 | leftwards arrow with medium triangle arrowhead | arrow_left |
| 🠅 | 1F805 | upwards arrow with medium triangle arrowhead | arrow_drop_up |
| 🠆 | 1F806 | rightwards arrow with medium triangle arrowhead | arrow_right |
| 🠇 | 1F807 | downwards arrow with medium triangle arrowhead | arrow_drop_down |
| 🠈 | 1F808 | leftwards arrow with large triangle arrowhead | arrow_left |
| 🠉 | 1F809 | upwards arrow with large triangle arrowhead | arrow_drop_up |
| 🠊 | 1F80A | rightwards arrow with large triangle arrowhead | arrow_right |
| 🠋 | 1F80B | downwards arrow with large triangle arrowhead | arrow_drop_down |
| 🠐 | 1F810 | leftwards arrow with small equilateral arrowhead | arrow_back |
| 🠑 | 1F811 | upwards arrow with small equilateral arrowhead | arrow_upward |
| 🠒 | 1F812 | rightwards arrow with small equilateral arrowhead | arrow_forward |
| 🠓 | 1F813 | downwards arrow with small equilateral arrowhead | arrow_downward |
| 🠔 | 1F814 | leftwards arrow with equilateral arrowhead | arrow_back |
| 🠕 | 1F815 | upwards arrow with equilateral arrowhead | arrow_upward |
| 🠖 | 1F816 | rightwards arrow with equilateral arrowhead | arrow_forward |
| 🠗 | 1F817 | downwards arrow with equilateral arrowhead | arrow_downward |
| 🠘 | 1F818 | heavy leftwards arrow with equilateral arrowhead | arrow_back |
| 🠙 | 1F819 | heavy upwards arrow with equilateral arrowhead | arrow_upward |
| 🠚 | 1F81A | heavy rightwards arrow with equilateral arrowhead | arrow_forward |
| 🠛 | 1F81B | heavy downwards arrow with equilateral arrowhead | arrow_downward |
| 🠜 | 1F81C | heavy leftwards arrow with large equilateral arrowhead | arrow_back |
| 🠝 | 1F81D | heavy upwards arrow with large equilateral arrowhead | arrow_upward |
| 🠞 | 1F81E | heavy rightwards arrow with large equilateral arrowhead | arrow_forward |
| 🠟 | 1F81F | heavy downwards arrow with large equilateral arrowhead | arrow_downward |
| 🠠 | 1F820 | leftwards triangle-headed arrow with narrow shaft | arrow_back |
| 🠡 | 1F821 | upwards triangle-headed arrow with narrow shaft | arrow_upward |
| 🠢 | 1F822 | rightwards triangle-headed arrow with narrow shaft | arrow_forward |
| 🠣 | 1F823 | downwards triangle-headed arrow with narrow shaft | arrow_downward |
| 🠤 | 1F824 | leftwards triangle-headed arrow with medium shaft | arrow_back |
| 🠥 | 1F825 | upwards triangle-headed arrow with medium shaft | arrow_upward |
| 🠦 | 1F826 | rightwards triangle-headed arrow with medium shaft | arrow_forward |
| 🠧 | 1F827 | downwards triangle-headed arrow with medium shaft | arrow_downward |
| 🠨 | 1F828 | leftwards triangle-headed arrow with bold shaft | arrow_back |
| 🠩 | 1F829 | upwards triangle-headed arrow with bold shaft | arrow_upward |
| 🠪 | 1F82A | rightwards triangle-headed arrow with bold shaft | arrow_forward |
| 🠫 | 1F82B | downwards triangle-headed arrow with bold shaft | arrow_downward |
| 🠬 | 1F82C | leftwards triangle-headed arrow with heavy shaft | arrow_back |
| 🠭 | 1F82D | upwards triangle-headed arrow with heavy shaft | arrow_upward |
| 🠮 | 1F82E | rightwards triangle-headed arrow with heavy shaft | arrow_forward |
| 🠯 | 1F82F | downwards triangle-headed arrow with heavy shaft | arrow_downward |
| 🠰 | 1F830 | leftwards triangle-headed arrow with very heavy shaft | arrow_back |
| 🠱 | 1F831 | upwards triangle-headed arrow with very heavy shaft | arrow_upward |
| 🠲 | 1F832 | rightwards triangle-headed arrow with very heavy shaft | arrow_forward |
| 🠳 | 1F833 | downwards triangle-headed arrow with very heavy shaft | arrow_downward |
| 🠴 | 1F834 | leftwards finger-post arrow | arrow_back |
| 🠵 | 1F835 | upwards finger-post arrow | arrow_upward |
| 🠶 | 1F836 | rightwards finger-post arrow | arrow_forward |
| 🠷 | 1F837 | downwards finger-post arrow | arrow_downward |
| 🠸 | 1F838 | leftwards squared arrow | arrow_back |
| 🠹 | 1F839 | upwards squared arrow | arrow_upward |
| 🠺 | 1F83A | rightwards squared arrow | arrow_forward |
| 🠻 | 1F83B | downwards squared arrow | arrow_downward |
| 🠼 | 1F83C | leftwards compressed arrow | arrow_back |
| 🠽 | 1F83D | upwards compressed arrow | arrow_upward |
| 🠾 | 1F83E | rightwards compressed arrow | arrow_forward |
| 🠿 | 1F83F | downwards compressed arrow | arrow_downward |
| 🡀 | 1F840 | leftwards heavy compressed arrow | arrow_back |
| 🡁 | 1F841 | upwards heavy compressed arrow | arrow_upward |
| 🡂 | 1F842 | rightwards heavy compressed arrow | arrow_forward |
| 🡃 | 1F843 | downwards heavy compressed arrow | arrow_downward |
| 🡄 | 1F844 | leftwards heavy arrow | arrow_back |
| 🡅 | 1F845 | upwards heavy arrow | arrow_upward |
| 🡆 | 1F846 | rightwards heavy arrow | arrow_forward |
| 🡇 | 1F847 | downwards heavy arrow | arrow_downward |
| 🡐 | 1F850 | leftwards sans-serif arrow | arrow_back |
| 🡑 | 1F851 | upwards sans-serif arrow | arrow_upward |
| 🡒 | 1F852 | rightwards sans-serif arrow | arrow_forward |
| 🡓 | 1F853 | downwards sans-serif arrow | arrow_downward |
| 🡔 | 1F854 | north west sans-serif arrow | north_west |
| 🡕 | 1F855 | north east sans-serif arrow | north_east |
| 🡖 | 1F856 | south east sans-serif arrow | south_east |
| 🡗 | 1F857 | south west sans-serif arrow | south_west |
| 🡘 | 1F858 | left right sans-serif arrow | arrow_range |
| 🡙 | 1F859 | up down sans-serif arrow | swap_vert |
| 🡠 | 1F860 | wide-headed leftwards light barb arrow | arrow_back |
| 🡡 | 1F861 | wide-headed upwards light barb arrow | arrow_upward |
| 🡢 | 1F862 | wide-headed rightwards light barb arrow | arrow_forward |
| 🡣 | 1F863 | wide-headed downwards light barb arrow | arrow_downward |
| 🡤 | 1F864 | wide-headed north west light barb arrow | north_west |
| 🡥 | 1F865 | wide-headed north east light barb arrow | north_east |
| 🡦 | 1F866 | wide-headed south east light barb arrow | south_east |
| 🡧 | 1F867 | wide-headed south west light barb arrow | south_west |
| 🡨 | 1F868 | wide-headed leftwards barb arrow | arrow_back |
| 🡩 | 1F869 | wide-headed upwards barb arrow | arrow_upward |
| 🡪 | 1F86A | wide-headed rightwards barb arrow | arrow_forward |
| 🡫 | 1F86B | wide-headed downwards barb arrow | arrow_downward |
| 🡬 | 1F86C | wide-headed north west barb arrow | north_west |
| 🡭 | 1F86D | wide-headed north east barb arrow | north_east |
| 🡮 | 1F86E | wide-headed south east barb arrow | south_east |
| 🡯 | 1F86F | wide-headed south west barb arrow | south_west |
| 🡰 | 1F870 | wide-headed leftwards medium barb arrow | arrow_back |
| 🡱 | 1F871 | wide-headed upwards medium barb arrow | arrow_upward |
| 🡲 | 1F872 | wide-headed rightwards medium barb arrow | arrow_forward |
| 🡳 | 1F873 | wide-headed downwards medium barb arrow | arrow_downward |
| 🡴 | 1F874 | wide-headed north west medium barb arrow | north_west |
| 🡵 | 1F875 | wide-headed north east medium barb arrow | north_east |
| 🡶 | 1F876 | wide-headed south east medium barb arrow | south_east |
| 🡷 | 1F877 | wide-headed south west medium barb arrow | south_west |
| 🡸 | 1F878 | wide-headed leftwards heavy barb arrow | arrow_back |
| 🡹 | 1F879 | wide-headed upwards heavy barb arrow | arrow_upward |
| 🡺 | 1F87A | wide-headed rightwards heavy barb arrow | arrow_forward |
| 🡻 | 1F87B | wide-headed downwards heavy barb arrow | arrow_downward |
| 🡼 | 1F87C | wide-headed north west heavy barb arrow | north_west |
| 🡽 | 1F87D | wide-headed north east heavy barb arrow | north_east |
| 🡾 | 1F87E | wide-headed south east heavy barb arrow | south_east |
| 🡿 | 1F87F | wide-headed south west heavy barb arrow | south_west |
| 🢀 | 1F880 | wide-headed leftwards very heavy barb arrow | arrow_back |
| 🢁 | 1F881 | wide-headed upwards very heavy barb arrow | arrow_upward |
| 🢂 | 1F882 | wide-headed rightwards very heavy barb arrow | arrow_forward |
| 🢃 | 1F883 | wide-headed downwards very heavy barb arrow | arrow_downward |
| 🢄 | 1F884 | wide-headed north west very heavy barb arrow | north_west |
| 🢅 | 1F885 | wide-headed north east very heavy barb arrow | north_east |
| 🢆 | 1F886 | wide-headed south east very heavy barb arrow | south_east |
| 🢇 | 1F887 | wide-headed south west very heavy barb arrow | south_west |
| 🢐 | 1F890 | leftwards triangle arrowhead | arrow_left |
| 🢑 | 1F891 | upwards triangle arrowhead | arrow_drop_up |
| 🢒 | 1F892 | rightwards triangle arrowhead | arrow_right |
| 🢓 | 1F893 | downwards triangle arrowhead | arrow_drop_down |
| 🢔 | 1F894 | leftwards white arrow within triangle arrowhead | arrow_left |
| 🢕 | 1F895 | upwards white arrow within triangle arrowhead | arrow_drop_up |
| 🢖 | 1F896 | rightwards white arrow within triangle arrowhead | arrow_right |
| 🢗 | 1F897 | downwards white arrow within triangle arrowhead | arrow_drop_down |
| 🢘 | 1F898 | leftwards arrow with notched tail | arrow_back |
| 🢙 | 1F899 | upwards arrow with notched tail | arrow_upward |
| 🢚 | 1F89A | rightwards arrow with notched tail | arrow_forward |
| 🢛 | 1F89B | downwards arrow with notched tail | arrow_downward |
| 🢜 | 1F89C | heavy arrow shaft width one | arrow_forward |
| 🢝 | 1F89D | heavy arrow shaft width two thirds | arrow_forward |
| 🢞 | 1F89E | heavy arrow shaft width one half | arrow_forward |
| 🢟 | 1F89F | heavy arrow shaft width one third | arrow_forward |
| 🢠 | 1F8A0 | leftwards bottom-shaded white arrow | arrow_back |
| 🢡 | 1F8A1 | rightwards bottom shaded white arrow | arrow_forward |
| 🢢 | 1F8A2 | leftwards top shaded white arrow | arrow_back |
| 🢣 | 1F8A3 | rightwards top shaded white arrow | arrow_forward |
| 🢤 | 1F8A4 | leftwards left-shaded white arrow | arrow_back |
| 🢥 | 1F8A5 | rightwards right-shaded white arrow | arrow_forward |
| 🢦 | 1F8A6 | leftwards right-shaded white arrow | arrow_back |
| 🢧 | 1F8A7 | rightwards left-shaded white arrow | arrow_forward |
| 🢨 | 1F8A8 | leftwards back-tilted shadowed white arrow | arrow_back |
| 🢩 | 1F8A9 | rightwards back-tilted shadowed white arrow | arrow_forward |
| 🢪 | 1F8AA | leftwards front-tilted shadowed white arrow | arrow_back |
| 🢫 | 1F8AB | rightwards front-tilted shadowed white arrow | arrow_forward |
| 🢬 | 1F8AC | white arrow shaft width one | arrow_forward |
| 🢭 | 1F8AD | white arrow shaft width two thirds | arrow_forward |
| 🢰 | 1F8B0 | arrow pointing upwards then north west | north_west |
| 🢱 | 1F8B1 | arrow pointing rightwards then curving south west | turn_slight_left |
| 🤀 | 1F900 | circled cross formee with four dots | add_circle |
| 🤁 | 1F901 | circled cross formee with two dots | add_circle |
| 🤂 | 1F902 | circled cross formee | add_circle |
| 🤃 | 1F903 | left half circle with four dots | circle |
| 🤄 | 1F904 | left half circle with three dots | circle |
| 🤅 | 1F905 | left half circle with two dots | circle |
| 🤆 | 1F906 | left half circle with dot | circle |
| 🤇 | 1F907 | left half circle | circle |
| 🤈 | 1F908 | downward facing hook | turn_right |
| 🤉 | 1F909 | downward facing notched hook | turn_right |
| 🤊 | 1F90A | downward facing hook with dot | turn_right |
| 🤋 | 1F90B | downward facing notched hook with dot | turn_right |
| 🤻 | 1F93B | modern pentathlon | sports |
| 🥆 | 1F946 | rifle | sports_score |
| 🨀 | 1FA00 | neutral chess king | chess |
| 🨁 | 1FA01 | neutral chess queen | chess |
| 🨂 | 1FA02 | neutral chess rook | chess |
| 🨃 | 1FA03 | neutral chess bishop | chess |
| 🨄 | 1FA04 | neutral chess knight | chess |
| 🨅 | 1FA05 | neutral chess pawn | chess |
| 🨆 | 1FA06 | white chess knight rotated forty-five degrees | chess:outlined |
| 🨇 | 1FA07 | black chess knight rotated forty-five degrees | chess:filled |
| 🨈 | 1FA08 | neutral chess knight rotated forty-five degrees | chess |
| 🨉 | 1FA09 | white chess king rotated ninety degrees | chess:outlined |
| 🨊 | 1FA0A | white chess queen rotated ninety degrees | chess:outlined |
| 🨋 | 1FA0B | white chess rook rotated ninety degrees | chess:outlined |
| 🨌 | 1FA0C | white chess bishop rotated ninety degrees | chess:outlined |
| 🨍 | 1FA0D | white chess knight rotated ninety degrees | chess:outlined |
| 🨎 | 1FA0E | white chess pawn rotated ninety degrees | chess:outlined |
| 🨏 | 1FA0F | black chess king rotated ninety degrees | chess:filled |
| 🨐 | 1FA10 | black chess queen rotated ninety degrees | chess:filled |
| 🨑 | 1FA11 | black chess rook rotated ninety degrees | chess:filled |
| 🨒 | 1FA12 | black chess bishop rotated ninety degrees | chess:filled |
| 🨓 | 1FA13 | black chess knight rotated ninety degrees | chess:filled |
| 🨔 | 1FA14 | black chess pawn rotated ninety degrees | chess:filled |
| 🨕 | 1FA15 | neutral chess king rotated ninety degrees | chess |
| 🨖 | 1FA16 | neutral chess queen rotated ninety degrees | chess |
| 🨗 | 1FA17 | neutral chess rook rotated ninety degrees | chess |
| 🨘 | 1FA18 | neutral chess bishop rotated ninety degrees | chess |
| 🨙 | 1FA19 | neutral chess knight rotated ninety degrees | chess |
| 🨚 | 1FA1A | neutral chess pawn rotated ninety degrees | chess |
| 🨛 | 1FA1B | white chess knight rotated one hundred thirty-five degrees | chess:outlined |
| 🨜 | 1FA1C | black chess knight rotated one hundred thirty-five degrees | chess:filled |
| 🨝 | 1FA1D | neutral chess knight rotated one hundred thirty-five degrees | chess |
| 🨞 | 1FA1E | white chess turned king | chess:outlined |
| 🨟 | 1FA1F | white chess turned queen | chess:outlined |
| 🨠 | 1FA20 | white chess turned rook | chess:outlined |
| 🨡 | 1FA21 | white chess turned bishop | chess:outlined |
| 🨢 | 1FA22 | white chess turned knight | chess:outlined |
| 🨣 | 1FA23 | white chess turned pawn | chess:outlined |
| 🨤 | 1FA24 | black chess turned king | chess:filled |
| 🨥 | 1FA25 | black chess turned queen | chess:filled |
| 🨦 | 1FA26 | black chess turned rook | chess:filled |
| 🨧 | 1FA27 | black chess turned bishop | chess:filled |
| 🨨 | 1FA28 | black chess turned knight | chess:filled |
| 🨩 | 1FA29 | black chess turned pawn | chess:filled |
| 🨪 | 1FA2A | neutral chess turned king | chess |
| 🨫 | 1FA2B | neutral chess turned queen | chess |
| 🨬 | 1FA2C | neutral chess turned rook | chess |
| 🨭 | 1FA2D | neutral chess turned bishop | chess |
| 🨮 | 1FA2E | neutral chess turned knight | chess |
| 🨯 | 1FA2F | neutral chess turned pawn | chess |
| 🨰 | 1FA30 | white chess knight rotated two hundred twenty-five degrees | chess:outlined |
| 🨱 | 1FA31 | black chess knight rotated two hundred twenty-five degrees | chess:filled |
| 🨲 | 1FA32 | neutral chess knight rotated two hundred twenty-five degrees | chess |
| 🨳 | 1FA33 | white chess king rotated two hundred seventy degrees | chess:outlined |
| 🨴 | 1FA34 | white chess queen rotated two hundred seventy degrees | chess:outlined |
| 🨵 | 1FA35 | white chess rook rotated two hundred seventy degrees | chess:outlined |
| 🨶 | 1FA36 | white chess bishop rotated two hundred seventy degrees | chess:outlined |
| 🨷 | 1FA37 | white chess knight rotated two hundred seventy degrees | chess:outlined |
| 🨸 | 1FA38 | white chess pawn rotated two hundred seventy degrees | chess:outlined |
| 🨹 | 1FA39 | black chess king rotated two hundred seventy degrees | chess:filled |
| 🨺 | 1FA3A | black chess queen rotated two hundred seventy degrees | chess:filled |
| 🨻 | 1FA3B | black chess rook rotated two hundred seventy degrees | chess:filled |
| 🨼 | 1FA3C | black chess bishop rotated two hundred seventy degrees | chess:filled |
| 🨽 | 1FA3D | black chess knight rotated two hundred seventy degrees | chess:filled |
| 🨾 | 1FA3E | black chess pawn rotated two hundred seventy degrees | chess:filled |
| 🨿 | 1FA3F | neutral chess king rotated two hundred seventy degrees | chess |
| 🩀 | 1FA40 | neutral chess queen rotated two hundred seventy degrees | chess |
| 🩁 | 1FA41 | neutral chess rook rotated two hundred seventy degrees | chess |
| 🩂 | 1FA42 | neutral chess bishop rotated two hundred seventy degrees | chess |
| 🩃 | 1FA43 | neutral chess knight rotated two hundred seventy degrees | chess |
| 🩄 | 1FA44 | neutral chess pawn rotated two hundred seventy degrees | chess |
| 🩅 | 1FA45 | white chess knight rotated three hundred fifteen degrees | chess:outlined |
| 🩆 | 1FA46 | black chess knight rotated three hundred fifteen degrees | chess:filled |
| 🩇 | 1FA47 | neutral chess knight rotated three hundred fifteen degrees | chess |
| 🩈 | 1FA48 | white chess equihopper | chess:outlined |
| 🩉 | 1FA49 | black chess equihopper | chess:filled |
| 🩊 | 1FA4A | neutral chess equihopper | chess |
| 🩋 | 1FA4B | white chess equihopper rotated ninety degrees | chess:outlined |
| 🩌 | 1FA4C | black chess equihopper rotated ninety degrees | chess:filled |
| 🩍 | 1FA4D | neutral chess equihopper rotated ninety degrees | chess |
| 🩎 | 1FA4E | white chess knight-queen | chess:outlined |
| 🩏 | 1FA4F | white chess knight-rook | chess:outlined |
| 🩐 | 1FA50 | white chess knight-bishop | chess:outlined |
| 🩑 | 1FA51 | black chess knight-queen | chess:filled |
| 🩒 | 1FA52 | black chess knight-rook | chess:filled |
| 🩓 | 1FA53 | black chess knight-bishop | chess:filled |
| 🩠 | 1FA60 | xiangqi red general | chess:outlined |
| 🩡 | 1FA61 | xiangqi red mandarin | chess:outlined |
| 🩢 | 1FA62 | xiangqi red elephant | chess:outlined |
| 🩣 | 1FA63 | xiangqi red horse | chess:outlined |
| 🩤 | 1FA64 | xiangqi red chariot | chess:outlined |
| 🩥 | 1FA65 | xiangqi red cannon | chess:outlined |
| 🩦 | 1FA66 | xiangqi red soldier | chess:outlined |
| 🩧 | 1FA67 | xiangqi black general | chess:filled |
| 🩨 | 1FA68 | xiangqi black mandarin | chess:filled |
| 🩩 | 1FA69 | xiangqi black elephant | chess:filled |
| 🩪 | 1FA6A | xiangqi black horse | chess:filled |
| 🩫 | 1FA6B | xiangqi black chariot | chess:filled |
| 🩬 | 1FA6C | xiangqi black cannon | chess:filled |
| 🩭 | 1FA6D | xiangqi black soldier | chess:filled |
| 🏁 | 1F3C1 | chequered flag | flag |
| 🚩 | 1F6A9 | triangular flag | flag |
| 🎌 | 1F38C | crossed flags | flag |
| 🏴 | 1F3F4 | black flag | flag |
| 🏳️ | 1F3F3 FE0F | white flag | flag |
| 🏳️‍🌈 | 1F3F3 FE0F 200D 1F308 | rainbow flag | flag |
| 🏳️‍⚧️ | 1F3F3 FE0F 200D 26A7 FE0F | transgender flag | flag |
| 🏴‍☠️ | 1F3F4 200D 2620 FE0F | pirate flag | flag |
| 🫱‍🫲 | 1FAF1 200D 1FAF2 | handshake, toneless form of the mixed-tone sequences | handshake |
| 👩‍🤝‍👩 | 1F469 200D 1F91D 200D 1F469 | women holding hands, toneless form of the mixed-tone sequences | group |
| 👩‍🤝‍👨 | 1F469 200D 1F91D 200D 1F468 | woman and man holding hands, toneless form of the mixed-tone sequences | group |
| 👨‍🤝‍👨 | 1F468 200D 1F91D 200D 1F468 | men holding hands, toneless form of the mixed-tone sequences | group |
| 🧑‍❤‍💋‍🧑 | 1F9D1 200D 2764 200D 1F48B 200D 1F9D1 | kiss, toneless form of the mixed-tone sequences | favorite |
| 🧑‍❤‍🧑 | 1F9D1 200D 2764 200D 1F9D1 | couple with heart, toneless form of the mixed-tone sequences | favorite |
| 🦰 | 1F9B0 | red hair | face |
| 🦱 | 1F9B1 | curly hair | face |
| 🦳 | 1F9B3 | white hair | face |
| 🦲 | 1F9B2 | bald | face |
