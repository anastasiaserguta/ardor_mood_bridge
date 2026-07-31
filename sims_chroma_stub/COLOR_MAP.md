# Sims Chroma Stub Color Map

The Sims 4 calls Chroma animations by file name, not by mood name.
This stub maps known Sims emotion names and the available keyboard animation names to whole-keyboard ARDOR colors.

## Full Emotion Palette

| Emotion | Hex | RGB |
| --- | --- | ---: |
| Angry | `#C3192B` | `195,25,43` |
| Uncomfortable | `#E26246` | `226,98,70` |
| Tense | `#DF841C` | `223,132,28` |
| Embarrassed | `#E1C043` | `225,192,67` |
| Energized | `#9DC948` | `157,201,72` |
| Happy | `#28B552` | `40,181,82` |
| Inspired | `#33BCC1` | `51,188,193` |
| Confident | `#448CC8` | `68,140,200` |
| Sad | `#2C44AA` | `44,68,170` |
| Focused | `#7038EC` | `112,56,236` |
| Dazed | `#816DCC` | `129,109,204` |
| Playful | `#B646AD` | `182,70,173` |
| Flirty | `#EE5DA5` | `238,93,165` |
| Scared | `#7E1260` | `126,18,96` |
| Bored | `#818785` | `129,135,133` |
| Fine | `#E9E9E9` | `233,233,233` |
| Asleep / Possessed / Recharge | `#4D4D70` | `77,77,112` |

## Current Sims Chroma Animation Mapping

| Sims Chroma animation | RGB | Intended mood family |
| --- | ---: | --- |
| `Idle_Keyboard.chroma` | `40,181,82` | happy, `#28B552` |
| `ShowEffect1_Keyboard.chroma` | `195,25,43` | angry, `#C3192B` |
| `ShowEffect2_Keyboard.chroma` | `223,132,28` | tense, `#DF841C` |
| `ShowEffect3_Keyboard.chroma` | `44,68,170` | sad, `#2C44AA` |
| `ShowEffect4_Keyboard.chroma` | `51,188,193` | inspired, `#33BCC1` |
| `ShowEffect5_Keyboard.chroma` | `112,56,236` | focused, `#7038EC` |
| `ShowEffect6_Keyboard.chroma` | `238,93,165` | flirty, `#EE5DA5` |
| `Blank_Keyboard.chroma` | ignored | keep previous color |

If the game always sends the same `ShowEffectN_Keyboard.chroma` for several moods, the stub cannot distinguish those moods yet.
The next step would be intercepting deeper frame/effect calls instead of only animation names.
