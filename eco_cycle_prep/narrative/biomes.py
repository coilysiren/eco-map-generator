"""Per-biome highlights: trees, fauna, minerals, and a one-line
gameplay hook. Used by text._paragraph_biome_contents to turn a biome
name into player-facing color ("oak and elk on granite, the classic
logging bootstrap") instead of just "warm forest."

Keyed by the biome-soil kind used everywhere else in the pipeline
(see blocks.BIOME_SOIL_KINDS). Source content is distilled from
docs/biomes.md; update both files together when the ground truth
changes.

Style rules for the four fields:

- Each field is a short, atomic descriptive phrase (no em-dashes, no
  parenthetical asides, no full sentences). The narrative composer
  slots them into a sentence template, so any internal em-dash would
  collide with the template's own punctuation.
- `trees`, `fauna`, and `minerals` include a positional hint where
  helpful ("overhead", "on the ground", "at depth", "over shallow
  copper") so the reader can tell which list is which even when two
  phrases share commas.
- `character` is the industry / gameplay hook in noun-phrase form
  (e.g. "tropical farming and gold mining"), not a verb sentence.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BiomeHighlight:
    trees: str       # canopy / headline flora
    fauna: str       # headline animals
    minerals: str    # surface stone + key ores
    character: str   # industry / gameplay hook, noun-phrase form


BIOME_HIGHLIGHTS: dict[str, BiomeHighlight] = {
    "grassland": BiomeHighlight(
        trees="scattered oaks over open plains",
        fauna="bison and elk on the ground, prairie dogs and turkeys underfoot",
        minerals="limestone and sandstone surface with coal and deep iron",
        character="a balanced wheat-and-bison start",
    ),
    "warm_forest": BiomeHighlight(
        trees="oak and birch overhead",
        fauna="elk and deer on the ground, wolves in the shadows",
        minerals="granite cliffs with copper in the midrange",
        character="the classic logging-and-copper bootstrap",
    ),
    "cold_forest": BiomeHighlight(
        trees="redwood, fir, and spruce overhead",
        fauna="elk, deer, and wolves",
        minerals="granite cliffs over shallow copper and deep gold",
        character="premium logging and late-game gold mining",
    ),
    "rainforest": BiomeHighlight(
        trees="ceiba and palm overhead",
        fauna="agouti on the ground and jaguars above",
        minerals="shale over gold at every depth",
        character="tropical farming and gold mining",
    ),
    "wetland": BiomeHighlight(
        trees="no canopy to speak of",
        fauna="otters and snapping turtles at the water",
        minerals="peat and shale over shallow coal",
        character="the wild-cotton biome, the one way to unlock textiles without imports",
    ),
    "taiga": BiomeHighlight(
        trees="spruce and arctic willow rooted in permafrost",
        fauna="elk and mountain goats, with wolves on the ridges",
        minerals="granite cliffs over shallow copper and deep gold",
        character="highland mining, though farming struggles on frozen soil",
    ),
    "tundra": BiomeHighlight(
        trees="dwarf willow only",
        fauna="mountain goats and wolves",
        minerals="gneiss surface with sulfur columns and late-game ore",
        character="pure extraction territory, where settlers need imported calories",
    ),
    "ice": BiomeHighlight(
        trees="no vegetation",
        fauna="no fauna on the sheet itself",
        minerals="a copper column sitting under the ice",
        character="a biome to cross, not to settle",
    ),
    "snow": BiomeHighlight(
        trees="no vegetation",
        fauna="no fauna",
        minerals="copper under the snow",
        character="usually just the capped peaks of a taiga or ice biome",
    ),
    "desert": BiomeHighlight(
        trees="joshua tree and saguaro on the surface",
        fauna="bighorn sheep and tortoises",
        minerals="iron from the surface down to 50 meters",
        character="the world's iron belt",
    ),
}
