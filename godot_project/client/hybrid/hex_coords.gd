extends RefCounted
class_name HybridHexCoords

## Fixed-point copy of WizardRTSHybrid/wizard_rts/coords.py.
## Integer division matches Python floor division, including negatives.

const MAP_Q := 20
const MAP_R := 20
const MILLI := 1000
const SIZE := 16 * MILLI
const SQRT3_OVER_3_MILLI := 577


static func floor_div(numer: int, denom: int) -> int:
	var q := int(float(numer) / float(denom))
	if (numer < 0) != (denom < 0) and q * denom != numer:
		q -= 1
	return q


static func div_round(numer: int, denom: int) -> int:
	var half := int(float(denom) / 2.0)
	if numer >= 0:
		return floor_div(numer + half, denom)
	return -floor_div(-numer + half, denom)


static func cube_round(x_milli: int, y_milli: int, z_milli: int) -> Vector3i:
	var rx := div_round(x_milli, MILLI)
	var ry := div_round(y_milli, MILLI)
	var rz := div_round(z_milli, MILLI)
	var dx := absi(rx * MILLI - x_milli)
	var dy := absi(ry * MILLI - y_milli)
	var dz := absi(rz * MILLI - z_milli)
	if dx > dy and dx > dz:
		rx = -ry - rz
	elif dy > dz:
		ry = -rx - rz
	else:
		rz = -rx - ry
	return Vector3i(rx, ry, rz)


static func tile_to_hex(tx: int, ty: int) -> Vector2i:
	var x := tx * MILLI + int(float(MILLI) / 2.0)
	var y := ty * MILLI + MILLI / 2
	var q_milli := floor_div(SQRT3_OVER_3_MILLI * x - floor_div(y * MILLI, 3), SIZE)
	var r_milli := floor_div(floor_div(2 * MILLI * y, 3), SIZE)
	var cube := cube_round(q_milli, -q_milli - r_milli, r_milli)
	return Vector2i(cube.x, cube.z)


static func in_map(q: int, r: int) -> bool:
	return q >= 0 and q < MAP_Q and r >= 0 and r < MAP_R


static func tile_in_map(tx: int, ty: int) -> bool:
	var hex := tile_to_hex(tx, ty)
	return in_map(hex.x, hex.y)
