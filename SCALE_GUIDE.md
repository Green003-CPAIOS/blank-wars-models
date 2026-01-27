# Character Model Scale Guide

Scale corrections for Metal Foldout Chair models based on visual audit (2026-01-26).

Base scale = 1.0 (standard human seated on chair)

## SCALE CORRECTIONS REQUIRED

| Character | Scale | Reason |
|-----------|-------|--------|
| crumbsworth | 0.5 | Toaster too large relative to chair/humans |
| rilak_trelkar | 0.75 | Small alien, should be shorter than humans |
| unicorn | 0.8 | Rearing horse extends very tall |
| velociraptor | 0.85 | Dinosaur crouching, slightly reduce |
| sun_wukong | 0.9 | Monkey King is compact |
| archangel_michael | 0.9 | Wings make model very wide |
| shaka_zulu | 1.1 | Sits lower than others, boost slightly |
| frankenstein | 1.1 | Monster should be larger than humans |
| quetzalcoatl | 1.15 | Serpent god coiled low, increase presence |
| fenrir | 1.3 | Giant mythological wolf, should be imposing |

## NO CHANGE NEEDED (Scale 1.0)

- achilles
- agent_x
- betty_boup
- billy_the_kid
- cleopatra
- don_quixote
- genghis_khan
- jack_the_ripper
- joan_of_arc
- kali
- kangaroo
- karna
- little_bo_peep
- mami_wata
- merlin
- napoleon
- nikola_tesla
- popeye
- pt_barnum
- ramses
- robin_hood
- sam_spade
- sherlock
- space_cyborg
- the_mad_hatter

## Usage in Code

```typescript
const CHARACTER_SCALE_CORRECTIONS: Record<string, number> = {
  'crumbsworth': 0.5,
  'rilak_trelkar': 0.75,
  'unicorn': 0.8,
  'velociraptor': 0.85,
  'sun_wukong': 0.9,
  'archangel_michael': 0.9,
  'shaka_zulu': 1.1,
  'frankenstein': 1.1,
  'quetzalcoatl': 1.15,
  'fenrir': 1.3,
};

export const getCharacterScaleCorrection = (name: string): number => {
  const normalized = name?.toLowerCase()?.trim();
  return CHARACTER_SCALE_CORRECTIONS[normalized] ?? 1.0;
};
```
