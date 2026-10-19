# Chess piece profiles

Parametric lines and circular arcs in the XY plane, with a terminal report that
refreshes when you save your Python source. Requires Python 3.14 and uv.

```sh
uv sync
```

The project pins Python 3.14 and installs CadQuery with its native OCP backend.

## Try the spreadsheet port

```sh
uv run profile-report examples/löpare.py
uv run profile-report examples/löpare.py --watch
```

Open `examples/löpare.py` in another terminal pane and edit/save it. The watcher
reevaluates the file from scratch, displaying each endpoint followed by its name
and, for arcs, `r=... centre=(...)`. Display values are rounded to two decimal places
with trailing zeros removed; calculations retain full floating-point precision.

The example ports the formulas in `löpare.xlsx`, not the rounded coordinates in
the original CAD model. The contour starts at the bottom, with X measuring
distance from the rotation axis and Y increasing toward the top. Profile methods
encapsulate the head, collar and stem constructions; the drawing has no helper
functions, intermediate geometry calculations or math imports. Its zero-radius
arc and zero-length line are omitted; the underside starts the contour and the
axis closes it.

The example includes edited base and tip dimensions. Tests verify those dimensions and
compare the unchanged stem, collar and head against the workbook's saved geometry,
accounting for the reversed traversal and vertical translation.

## Write a profile

A source file must define a variable named `profile`:

```python
from chess_pieces_3d import Profile, TANGENT_Y

profile = Profile(start=(0, 0))
profile.line(x=10, name="bottom")
profile.line(dy=2, name="rim")
base = profile.arc_pair(
    x=8,
    dy=2.5,
    start_tangent=profile.last_tangent,
    end_tangent=TANGENT_Y,
    turns=("ccw", "cw"),
    radius_ratio=2,
    name="base_transition",
)
```

- `x`/`y` are absolute coordinates; `dx`/`dy` are offsets from the current endpoint.
  Specifying both forms for the same axis is an error.
- Lines and compound constructions leave an omitted coordinate unchanged.
- Tangents are directed, nonzero vectors, normalized internally. `TANGENT_X` and
  `TANGENT_Y` point along the positive axes. CW/CCW use the usual X-right, Y-up
  convention, even when your drawing uses negative Y coordinates.
- Names are optional and otherwise assigned automatically. Explicit names must
  be unique, including the `.1`/`.2` names generated for an arc pair.
- Basic operations return immutable `Line`, `Arc` or `ArcPair` objects.
  `arc_via_extreme()` returns an immutable `ProfilePath` of arcs; `arc_line()`
  returns its arc and line as a tuple. Refer to objects
  directly rather than looking up strings: `base.first.radius`,
  `base.second.center`, `base.end`, `base.end_tangent`.
- `profile.start`, `profile.end`, `profile.last_tangent` and `profile.segments`
  expose the current geometry. An empty profile has no tangent.

### Fractional positions

`Profile`, `Line`, `Arc`, `ArcPair` and `ProfilePath` expose `length` (in mm) and
`point_at(fraction)`. Fractions range from 0 (start) to 1 (end) and measure **arc
length**, not height, chord distance or segment count. For a multi-segment part,
longer segments contribute proportionally.

```python
head = profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2, name="head")
start = head.point_at(0.2)
end = head.point_at(0.85)
```

`ProfilePath` retains tuple indexing and unpacking, so `head[0]` still gives its
first arc. It is a snapshot unaffected by later additions to the profile. Use
`ProfilePath(segments)` to sample any other connected sequence, such as the pair
returned by `arc_line()`. Invalid fractions, empty paths and disconnected paths
are rejected. These geometry methods do not load CadQuery.

### Single arcs

An endpoint and a start or end tangent determine the circle:

```python
profile = Profile()
arc = profile.arc(x=2, y=2, start_tangent=(1, 0))
# radius=2, center=(0, 2), turn="ccw"
```

Alternatively, give a radius, one endpoint coordinate, and a tangent. The other
coordinate is solved rather than held unchanged:

```python
profile = Profile()
arc = profile.arc(dx=-2, radius=3, start_tangent=(0, 1))
# end=(-2, sqrt(8)), center=(-3, 0), turn="ccw"
```

`end_tangent=...` works in either form. If neither tangent is provided, the start
tangent defaults to `profile.last_tangent`. Providing only an end tangent does
**not** also constrain the start tangent; this allows deliberate corners.

Without a supplied radius, an omitted endpoint coordinate stays unchanged.
With a radius, at least one coordinate must be supplied. You may supply both
coordinates, both tangents, or `turn="cw"`/`"ccw"` as additional constraints;
all must agree. The library never silently relaxes constraints.

### Arc pairs

`arc_pair()` constructs two opposite-turn arcs with a smooth internal join,
a required end tangent, and `radius_ratio = first.radius / second.radius`.
The start tangent defaults to the previous segment's end tangent. Explicitly
providing a different start tangent allows a corner with the preceding segment.

### Compound constructions

Keep the drawing declarative by expressing the entire construction in one call:

```python
profile.arc_via_extreme(
    x=6.5,
    dy=14,
    extreme_x=4,
    start_radius=1,
    end_radius=2,
    name="stem",
)
profile.arc_line(x=3.4, dy=2.5, radius=2, turn="ccw", name="collar")
profile.arc_via_extreme(x=2.5, dy=12.3, extreme_x=5.2, name="head")
```

- `arc_via_extreme()` solves a circle through an X maximum or minimum, optionally
  joined to endpoint fillets. `extreme_x` must be strictly to the same side of
  both endpoints; the extremum's Y lies between theirs. The circle is split at
  the extremum into `.before_extreme` and `.after_extreme` arcs.
- Positive `start_radius`/`end_radius` add `.start_fillet`/`.end_fillet` arcs with
  vertical endpoint tangents pointing toward the destination's Y. A start fillet
  must match the existing incoming tangent. A zero radius omits that fillet and
  leaves the corresponding endpoint tangent unconstrained. With neither fillet,
  only the two endpoints and `extreme_x` are needed.
- `arc_line()` adds `.arc` followed by `.line`, solving their tangent contact.
  Supply the arc's radius and turn, and the **line's final endpoint**. The start
  tangent defaults to `profile.last_tangent`, or can be supplied explicitly.

These methods support `x`/`dx` and `y`/`dy`, return segments in drawing order, and
append nothing unless the whole construction succeeds. Child names participate
in the same duplicate-name checks as ordinary segments.

All arcs must have a sweep strictly between 0 and 180 degrees. Impossible,
degenerate and ambiguous constructions raise `GeometryError`, including the
construction's name. Failed operations leave the profile unchanged. Major arcs
and general-purpose constraint solving are deliberately not supported.

### Reports and watching

Use `format_profile(profile)` to get the report as a string outside the CLI.

The watcher polls only the specified source file, not its imported dependencies.
It clears the display on a terminal and appends reports when redirected. Errors
include their Python traceback and source line; no old report is presented as a
successful current result. Save again to recover; Ctrl-C exits. Source files are
executed as ordinary Python, so only run files you trust.

## Revolve and export

`revolve_profile(profile)` returns a CadQuery `Solid`. It maps profile X to radius and Y to Z height, revolves 360 degrees about
Z, and preserves circular edges using three-point arcs. The contour must already
be closed and stay at nonnegative X, including between arc endpoints. Invalid or
multiple solids are rejected.

The example defines a `build_solid()` function; reporting never calls it. With a
working CadQuery installation, export it to `bishop.stl` in the current directory:

```sh
uv run python examples/löpare.py
```

Other callers can import the drawing and call `build_solid()` to perform further
CAD operations before exporting. Nothing is exported when the file is imported
or evaluated by `profile-report`.

CadQuery is imported inside solid-building and exporting functions, not at module
load time. Type annotations use `TYPE_CHECKING` imports. Importing the converter,
legacy model or drawing therefore does not load CadQuery, and reporting stays
lightweight. Both reporting and CAD generation run in the same Python 3.14
environment; no separate worker or custom native build is needed.

## Sand-like surface texture

```sh
uv run python examples/löpare_3d_print.py
```

This exports `löpare_3d_print.stl` with the existing magnet cavity and staggered
rings on a 90° sector, from 20% to 85% along the whole head by arc length. This
leaves the first 20% and last 15% bare; the selected curved surface is about 0.66 cm².
With the current drawing, 0.8 mm spacing and 0.2 mm ball radii, the command prints:

```text
Sand texture: 123 balls; 186.68 balls/cm² (surface patch: 0.66 cm²).
```

Importing the print example does not build or export anything; call its
`build_solid()` explicitly, or `build_solid(report=True)` to also print statistics.

### Staggered rings along a profile

```python
from chess_pieces_3d import ring_sand

patch = ring_sand(
    profile,
    start=head.point_at(0.2),
    end=head.point_at(0.85),
    angle=90,
    start_angle=-45,
    spacing=0.8,
    radius=0.2,
)
textured = solid.fuse(*patch.balls) if patch.balls else solid
print(patch.count, patch.area, patch.density_per_cm2)
```

`ring_sand()` returns a `SandPatch` with **unfused**, complete spheres. It does not
revolve, alter or fuse the input profile. The drawing stores the head construction
as `head = profile.arc_via_extreme(...)`, making its exact endpoints easy to reuse.

- `start` and `end` are exact `(X, Y)` points on the profile, including interiors
  of lines or arcs. They follow profile order; intervals do not wrap. Shared
  segment junctions are accepted, while off-profile or ambiguous points are
  rejected. On a closed contour, `start=profile.start, end=profile.end` selects
  the whole contour. Prefer construction `.start`/`.end` references to rounded
  report values.
- Fractional positions belong to the geometry: `head.point_at(0.2)` and
  `head.point_at(0.85)` leave the first 20% and final 15% of the whole head
  unsanded. `ring_sand()` only receives the resulting start and end points.
- Profile X becomes radius, and Y becomes Z height. Angles are degrees
  counterclockwise about Z from +X. `angle` defaults to 360; `start_angle` defaults
  to 0 and may be negative. These control coverage, not the solid's revolution.
- Rings are spaced by meridian **arc length**, targeting `spacing * sqrt(3)/2`.
  Ball counts target `spacing` around each circumference. Counts are rounded to
  fit, and alternate rings shift by half an angular step. There is no planar
  projection stretching, nor duplicate seam balls at 360°.
- Ring centres are inset by half a row from the interval ends. Axis-only portions
  contribute no area or rings. The selected profile must stay at nonnegative X.
  Spacing and radius are in mm; spacing must exceed the sphere diameter.
- `patch.balls` is a tuple of CAD shapes; `patch.count` is its length. `patch.area`
  is the selected **original curved surface area in mm²**, computed analytically
  as `radians(angle) * integral(radius * ds)` for the exact lines/arcs.
  `patch.density_per_cm2` is count divided by that area in cm², before display
  rounding. This is not the enlarged surface area of the bumps themselves.

The layout is approximately hexagonal, not a perfect geodesic lattice: changing
circumference and integer counts affect neighbours. Tight curvature, poles,
sharp corners and oversized balls still require care. Bounds apply to centres;
ball footprints can extend beyond them. The generator knows only the profile,
not later cuts: select a surface that still exists on the solid being textured.
CAD imports remain deferred until balls are generated.

Tests check the fused CAD solid, preservation of the original material and magnet
cavity, and STL mesh watertightness and winding. Mesh validation discards zero-area
triangles that OCCT can emit at spherical poles.

## Development

```sh
uv run python -m unittest discover -s tests -v
uv run ty check
uv run ruff check .
uv run ruff format --check .
```

The geometry, report and watcher use only the standard library. They do not load
CadQuery or rebuild a solid. The existing `chess-pieces-3d` STL-export command
is retained, with its original model now in `src/chess_pieces_3d/bishop.py`;
it still needs a working CadQuery/OCP installation.
