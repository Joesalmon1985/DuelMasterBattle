"""Independent oracle: contract expectations vs authority / render / image layers."""

from __future__ import annotations

from typing import Any


class OracleFailure(AssertionError):
    def __init__(self, code: str, message: str, *, layer: str, detail: dict | None = None):
        super().__init__(f"[{layer}/{code}] {message}")
        self.code = code
        self.layer = layer
        self.detail = detail or {}


def _entities_by_sim_id(render: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group harvested nodes by sim_id; preserve duplicates as list entries."""
    out: dict[str, list[dict[str, Any]]] = {}
    for ent in render.get("entities") or []:
        sid = str(ent.get("sim_id") or ent.get("id") or "")
        if not sid:
            continue
        out.setdefault(sid, []).append(ent)
    return out


def assert_authority_expectations(contract: dict[str, Any], authority: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("authority") or {}
    if not exp:
        return [{"assertion": "authority_none", "status": "PASS", "layer": "authority"}]

    if "min_buildings" in exp:
        n = int(authority.get("counts", {}).get("buildings") or 0)
        ok = n >= int(exp["min_buildings"])
        results.append(
            {
                "assertion": "min_buildings",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": exp["min_buildings"],
                "actual": n,
            }
        )
        if not ok:
            raise OracleFailure("min_buildings", f"buildings {n} < {exp['min_buildings']}", layer="authority")

    if "player_node_id" in exp:
        actual = authority.get("player_node_id")
        ok = actual == exp["player_node_id"]
        results.append(
            {
                "assertion": "player_node_id",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": exp["player_node_id"],
                "actual": actual,
            }
        )
        if not ok:
            raise OracleFailure("player_node_id", f"{actual} != {exp['player_node_id']}", layer="authority")

    if "min_units" in exp:
        n = int(authority.get("counts", {}).get("units") or 0)
        ok = n >= int(exp["min_units"])
        results.append(
            {
                "assertion": "min_units",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": exp["min_units"],
                "actual": n,
            }
        )
        if not ok:
            raise OracleFailure("min_units", f"units {n} < {exp['min_units']}", layer="authority")

    if "order_status" in exp:
        want = exp["order_status"]
        oid = want.get("id")
        status = want.get("status")
        order = (authority.get("orders") or {}).get(oid) if oid else None
        actual = (order or {}).get("status")
        ok = order is not None and actual == status
        results.append(
            {
                "assertion": "order_status",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": want,
                "actual": order,
            }
        )
        if not ok:
            raise OracleFailure("order_status", f"order {oid} status {actual}", layer="authority", detail={"order": order})

    if "committed_action" in exp:
        action = exp["committed_action"]
        hits = [
            o
            for o in (authority.get("orders") or {}).values()
            if o.get("action") == action and o.get("status") == "committed"
        ]
        ok = len(hits) >= int(exp.get("committed_min", 1))
        results.append(
            {
                "assertion": "committed_action",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": exp["committed_action"],
                "actual_count": len(hits),
            }
        )
        if not ok:
            raise OracleFailure("committed_action", f"no committed {action}", layer="authority")

    if "battle_states_any" in exp:
        allowed = set(exp["battle_states_any"])
        states = {str(b.get("state")) for b in (authority.get("battles") or {}).values()}
        ok = bool(states & allowed) if exp.get("require_battle", True) else True
        if exp.get("require_battle", True) and not (authority.get("battles") or {}):
            ok = False
        results.append(
            {
                "assertion": "battle_states_any",
                "status": "PASS" if ok else "FAIL",
                "layer": "authority",
                "expected": sorted(allowed),
                "actual": sorted(states),
            }
        )
        if not ok:
            raise OracleFailure("battle_states_any", f"states={states}", layer="authority")

    return results


def assert_render_expectations(contract: dict[str, Any], render: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("render") or {}
    if not exp:
        return [{"assertion": "render_none", "status": "PASS", "layer": "render"}]

    by_id = _entities_by_sim_id(render)

    if "require_sim_ids" in exp:
        for sid in exp["require_sim_ids"]:
            ents = by_id.get(sid) or []
            bodies = [e for e in ents if str(e.get("role") or "body") == "body"]
            ok = len(bodies) == 1
            code = "missing_render_entity" if not bodies else ("duplicate_render_entity" if len(bodies) > 1 else "ok")
            results.append(
                {
                    "assertion": "require_sim_id",
                    "status": "PASS" if ok else "FAIL",
                    "layer": "render",
                    "code": code,
                    "sim_id": sid,
                    "count": len(bodies),
                }
            )
            if not bodies:
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            if len(bodies) > 1:
                raise OracleFailure("duplicate_render_entity", f"sim_id={sid} count={len(bodies)}", layer="render")

    if "forbid_sim_ids" in exp:
        for sid in exp["forbid_sim_ids"]:
            ents = by_id.get(sid) or []
            if ents:
                results.append(
                    {
                        "assertion": "forbid_sim_id",
                        "status": "FAIL",
                        "layer": "render",
                        "code": "stale_render_entity",
                        "sim_id": sid,
                        "count": len(ents),
                    }
                )
                raise OracleFailure("stale_render_entity", f"sim_id={sid} still present", layer="render")
            results.append(
                {
                    "assertion": "forbid_sim_id",
                    "status": "PASS",
                    "layer": "render",
                    "code": "ok",
                    "sim_id": sid,
                }
            )

    if "min_entities" in exp:
        n = len(render.get("entities") or [])
        ok = n >= int(exp["min_entities"])
        results.append(
            {
                "assertion": "min_entities",
                "status": "PASS" if ok else "FAIL",
                "layer": "render",
                "expected": exp["min_entities"],
                "actual": n,
            }
        )
        if not ok:
            raise OracleFailure("missing_render_entity", f"entity count {n}", layer="render")

    if "kinds_present" in exp:
        kinds = {str(e.get("sim_kind") or e.get("kind") or "") for e in (render.get("entities") or [])}
        for kind in exp["kinds_present"]:
            ok = kind in kinds
            results.append(
                {
                    "assertion": "kind_present",
                    "status": "PASS" if ok else "FAIL",
                    "layer": "render",
                    "kind": kind,
                }
            )
            if not ok:
                raise OracleFailure("missing_render_entity", f"kind={kind}", layer="render")

    if "entity_visible" in exp:
        for sid in exp["entity_visible"]:
            ents = by_id.get(sid) or []
            if not ents:
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            visible = any(bool(e.get("visible_in_tree", e.get("visible", True))) for e in ents)
            in_view = any(bool(e.get("in_viewport", True)) for e in ents)
            if not visible or not in_view:
                raise OracleFailure(
                    "hidden_or_off_viewport",
                    f"sim_id={sid} visible={visible} in_viewport={in_view}",
                    layer="render",
                )
            results.append({"assertion": "entity_visible", "status": "PASS", "layer": "render", "sim_id": sid})

    if "grid_near" in exp:
        for row in exp["grid_near"]:
            sid = row["sim_id"]
            want = row["grid"]
            tol = float(row.get("tol", 1.5))
            ents = by_id.get(sid) or []
            if not ents:
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            pos = ents[0].get("grid") or ents[0].get("position_grid")
            if pos is None:
                raise OracleFailure("wrong_location", f"sim_id={sid} no grid", layer="render")
            dx = abs(float(pos[0]) - float(want[0]))
            dy = abs(float(pos[1]) - float(want[1]))
            if dx > tol or dy > tol:
                raise OracleFailure(
                    "wrong_location",
                    f"sim_id={sid} grid={pos} expected~{want}",
                    layer="render",
                    detail={"actual": pos, "expected": want},
                )
            results.append({"assertion": "grid_near", "status": "PASS", "layer": "render", "sim_id": sid})

    return results


def assert_image_expectations(contract: dict[str, Any], image_result: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("image") or {}
    if not exp:
        return [{"assertion": "image_none", "status": "PASS", "layer": "image"}]

    status = str(image_result.get("status") or "NOT_RUN")
    if status in {"ERROR", "NOT_RUN", "INCONCLUSIVE"}:
        if exp.get("allow_missing"):
            results.append({"assertion": "image_optional", "status": status, "layer": "image"})
            return results
        raise OracleFailure("blank_or_missing_screenshot", f"image status={status}", layer="image", detail=image_result)

    if status == "FAIL" or image_result.get("code") == "blank_or_missing_screenshot":
        raise OracleFailure(
            str(image_result.get("code") or "blank_or_missing_screenshot"),
            str(image_result.get("reason") or status),
            layer="image",
            detail=image_result,
        )

    if exp.get("require_nonblank", True) and image_result.get("near_blank"):
        raise OracleFailure("blank_or_missing_screenshot", "near_blank", layer="image", detail=image_result)

    if "min_bytes" in exp and int(image_result.get("bytes") or 0) < int(exp["min_bytes"]):
        raise OracleFailure(
            "blank_or_missing_screenshot",
            f"bytes={image_result.get('bytes')}",
            layer="image",
            detail=image_result,
        )

    results.append({"assertion": "image_ok", "status": "PASS", "layer": "image", "detail": image_result})
    return results


def run_oracle(
    contract: dict[str, Any],
    *,
    authority: dict[str, Any] | None = None,
    render: dict[str, Any] | None = None,
    image: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare independent expected contract to independent actual layers."""
    assertions: list[dict] = []
    failures: list[dict] = []
    try:
        if authority is not None:
            assertions.extend(assert_authority_expectations(contract, authority))
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})
    try:
        if render is not None:
            assertions.extend(assert_render_expectations(contract, render))
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})
    try:
        if image is not None:
            assertions.extend(assert_image_expectations(contract, image))
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})

    status = "FAIL" if failures else "PASS"
    return {
        "scenario_id": contract.get("scenario_id"),
        "scenario_class": contract.get("scenario_class"),
        "status": status,
        "assertions": assertions,
        "failures": failures,
    }
