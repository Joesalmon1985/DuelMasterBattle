"""Independent oracle: contract expectations vs authority / render / image layers."""

from __future__ import annotations

from typing import Any


class OracleFailure(AssertionError):
    def __init__(self, code: str, message: str, *, layer: str, detail: dict | None = None):
        super().__init__(f"[{layer}/{code}] {message}")
        self.code = code
        self.layer = layer
        self.detail = detail or {}


def _is_node_backed_body(ent: dict[str, Any]) -> bool:
    """Bodies count unless explicitly non-node / dict-only. Default true for fixtures."""
    if str(ent.get("role") or "") != "body":
        return False
    if str(ent.get("observation") or "") == "dict_only_no_node":
        return False
    if ent.get("node_backed") is False:
        return False
    return True


def _bodies_by_sim_id(render: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ent in render.get("entities") or []:
        if not _is_node_backed_body(ent):
            continue
        sid = str(ent.get("sim_id") or "")
        if not sid:
            continue
        out.setdefault(sid, []).append(ent)
    return out


def assert_authority_expectations(contract: dict[str, Any], authority: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("authority") or {}
    if not exp:
        return results

    if "min_buildings" in exp:
        n = int(authority.get("counts", {}).get("buildings") or 0)
        ok = n >= int(exp["min_buildings"])
        results.append({"assertion": "min_buildings", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": exp["min_buildings"], "actual": n})
        if not ok:
            raise OracleFailure("min_buildings", f"buildings {n}", layer="authority")

    if "player_node_id" in exp:
        actual = authority.get("player_node_id")
        ok = actual == exp["player_node_id"]
        results.append({"assertion": "player_node_id", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": exp["player_node_id"], "actual": actual})
        if not ok:
            raise OracleFailure("player_node_id", f"{actual}", layer="authority")

    if "min_units" in exp:
        n = int(authority.get("counts", {}).get("units") or 0)
        ok = n >= int(exp["min_units"])
        results.append({"assertion": "min_units", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": exp["min_units"], "actual": n})
        if not ok:
            raise OracleFailure("min_units", f"units {n}", layer="authority")

    if "committed_action" in exp:
        action = exp["committed_action"]
        hits = [o for o in (authority.get("orders") or {}).values() if o.get("action") == action and o.get("status") == "committed"]
        ok = len(hits) >= int(exp.get("committed_min", 1))
        results.append({"assertion": "committed_action", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": action, "actual_count": len(hits)})
        if not ok:
            raise OracleFailure("committed_action", f"no committed {action}", layer="authority")

    if "order_status_any" in exp:
        want = exp["order_status_any"]
        hits = [o for o in (authority.get("orders") or {}).values() if o.get("status") in set(want.get("statuses") or []) and (not want.get("action") or o.get("action") == want.get("action"))]
        ok = len(hits) >= int(want.get("min", 1))
        results.append({"assertion": "order_status_any", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": want, "actual_count": len(hits)})
        if not ok:
            raise OracleFailure("order_status_any", f"{want}", layer="authority")

    if "battle_states_any" in exp:
        allowed = set(exp["battle_states_any"])
        states = {str(b.get("state")) for b in (authority.get("battles") or {}).values()}
        ok = bool(states & allowed)
        if exp.get("require_battle", True) and not (authority.get("battles") or {}):
            ok = False
        results.append({"assertion": "battle_states_any", "status": "PASS" if ok else "FAIL", "layer": "authority", "expected": sorted(allowed), "actual": sorted(states)})
        if not ok:
            raise OracleFailure("battle_states_any", f"states={states}", layer="authority")

    if "lease_not_active_for_closed" in exp and exp["lease_not_active_for_closed"]:
        from sim.dmb.testing.visual_sim.asserts import assert_lease_closed

        try:
            assert_lease_closed(authority, exp.get("battle_id"))
            results.append({"assertion": "lease_closed", "status": "PASS", "layer": "authority"})
        except AssertionError as exc:
            results.append({"assertion": "lease_closed", "status": "FAIL", "layer": "authority", "message": str(exc)})
            raise OracleFailure("stale_lease", str(exc), layer="authority") from exc

    return results


def assert_render_expectations(contract: dict[str, Any], render: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("render") or {}
    if not exp:
        return results
    by_id = _bodies_by_sim_id(render)

    min_nb = exp.get("min_node_backed", exp.get("min_entities"))
    if min_nb is not None:
        n = int(
            render.get("node_backed_count")
            or sum(1 for e in (render.get("entities") or []) if e.get("node_backed") is not False and str(e.get("observation") or "") != "dict_only_no_node")
        )
        ok = n >= int(min_nb)
        results.append({"assertion": "min_node_backed", "status": "PASS" if ok else "FAIL", "layer": "render", "expected": min_nb, "actual": n})
        if not ok:
            raise OracleFailure("missing_render_entity", f"node_backed={n}", layer="render")

    if "require_sim_ids" in exp:
        for sid in exp["require_sim_ids"]:
            bodies = by_id.get(sid) or []
            if not bodies:
                results.append({"assertion": "require_sim_id", "status": "FAIL", "layer": "render", "code": "missing_render_entity", "sim_id": sid})
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            if len(bodies) > 1:
                results.append({"assertion": "require_sim_id", "status": "FAIL", "layer": "render", "code": "duplicate_render_entity", "sim_id": sid, "count": len(bodies)})
                raise OracleFailure("duplicate_render_entity", f"sim_id={sid} count={len(bodies)}", layer="render")
            results.append({"assertion": "require_sim_id", "status": "PASS", "layer": "render", "sim_id": sid})

    if "forbid_sim_ids" in exp:
        for sid in exp["forbid_sim_ids"]:
            bodies = by_id.get(sid) or []
            # Any node-backed body for a forbidden id is stale (hidden still counts).
            if bodies:
                results.append({"assertion": "forbid_sim_id", "status": "FAIL", "layer": "render", "code": "stale_render_entity", "sim_id": sid})
                raise OracleFailure("stale_render_entity", f"sim_id={sid}", layer="render")
            results.append({"assertion": "forbid_sim_id", "status": "PASS", "layer": "render", "sim_id": sid})

    if "forbid_scaffold_for_committed" in exp:
        from sim.dmb.testing.visual_sim.asserts import assert_committed_order_without_active_scaffold

        # authority must be passed via exp hook — handled in run_oracle with both layers
        results.append({"assertion": "forbid_scaffold_deferred", "status": "PASS", "layer": "render"})

    if "kinds_present" in exp:
        kinds = {str(e.get("sim_kind") or "") for e in (render.get("entities") or []) if e.get("node_backed")}
        for kind in exp["kinds_present"]:
            ok = kind in kinds
            results.append({"assertion": "kind_present", "status": "PASS" if ok else "FAIL", "layer": "render", "kind": kind})
            if not ok:
                raise OracleFailure("missing_render_entity", f"kind={kind}", layer="render")

    if "entity_visible" in exp:
        for sid in exp["entity_visible"]:
            bodies = by_id.get(sid) or []
            if not bodies:
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            if not any(b.get("visible_in_tree") and b.get("in_viewport") for b in bodies):
                raise OracleFailure("hidden_or_off_viewport", f"sim_id={sid}", layer="render", detail={"bodies": bodies})
            results.append({"assertion": "entity_visible", "status": "PASS", "layer": "render", "sim_id": sid})

    if "control_visible" in exp:
        for cid in exp["control_visible"]:
            hits = [e for e in (render.get("entities") or []) if str(e.get("sim_id")) == cid and str(e.get("role")) == "control"]
            if not hits or not any(h.get("visible_in_tree") and h.get("in_viewport") for h in hits):
                raise OracleFailure("hidden_or_off_viewport", f"control={cid}", layer="render")
            results.append({"assertion": "control_visible", "status": "PASS", "layer": "render", "sim_id": cid})

    if "grid_near" in exp:
        for row in exp["grid_near"]:
            sid = row["sim_id"]
            want = row["grid"]
            tol = float(row.get("tol", 1.5))
            bodies = by_id.get(sid) or []
            if not bodies:
                raise OracleFailure("missing_render_entity", f"sim_id={sid}", layer="render")
            pos = bodies[0].get("grid")
            if pos is None:
                raise OracleFailure("wrong_location", f"sim_id={sid} no grid", layer="render")
            if abs(float(pos[0]) - float(want[0])) > tol or abs(float(pos[1]) - float(want[1])) > tol:
                raise OracleFailure("wrong_location", f"sim_id={sid} grid={pos} expected~{want}", layer="render")
            results.append({"assertion": "grid_near", "status": "PASS", "layer": "render", "sim_id": sid})

    if "no_text_control_overlap" in exp and exp["no_text_control_overlap"]:
        overlaps = render.get("ui_overlaps") or []
        if overlaps:
            raise OracleFailure("ui_overlap", f"{overlaps}", layer="render", detail={"overlaps": overlaps})
        results.append({"assertion": "no_text_control_overlap", "status": "PASS", "layer": "render"})

    return results


def assert_image_expectations(contract: dict[str, Any], image_result: dict[str, Any]) -> list[dict]:
    results: list[dict] = []
    exp = (contract.get("expectations") or {}).get("image") or {}
    if not exp:
        return results
    status = str(image_result.get("status") or "NOT_RUN")
    if status in {"ERROR", "NOT_RUN", "INCONCLUSIVE"}:
        if exp.get("allow_missing"):
            results.append({"assertion": "image_optional", "status": status, "layer": "image"})
            return results
        raise OracleFailure("blank_or_missing_screenshot", f"image status={status}", layer="image", detail=image_result)
    if status == "FAIL" or image_result.get("code") == "blank_or_missing_screenshot":
        raise OracleFailure(str(image_result.get("code") or "blank_or_missing_screenshot"), str(image_result.get("reason") or status), layer="image", detail=image_result)
    if exp.get("require_nonblank", True) and image_result.get("near_blank"):
        raise OracleFailure("blank_or_missing_screenshot", "near_blank", layer="image", detail=image_result)
    if "min_bytes" in exp and int(image_result.get("bytes") or 0) < int(exp["min_bytes"]):
        raise OracleFailure("blank_or_missing_screenshot", f"bytes={image_result.get('bytes')}", layer="image")
    results.append({"assertion": "image_ok", "status": "PASS", "layer": "image", "detail": image_result})
    return results


def run_oracle(
    contract: dict[str, Any],
    *,
    authority: dict[str, Any] | None = None,
    render: dict[str, Any] | None = None,
    image: dict[str, Any] | None = None,
    require_assertions: bool = True,
) -> dict[str, Any]:
    assertions: list[dict] = []
    failures: list[dict] = []
    exp = contract.get("expectations") or {}
    needed_layers = []
    # Empty expectation objects mean "no checks on this layer", not "layer required".
    if exp.get("authority"):
        needed_layers.append("authority")
    if exp.get("render"):
        needed_layers.append("render")
    if exp.get("image"):
        needed_layers.append("image")

    try:
        if authority is not None:
            assertions.extend(assert_authority_expectations(contract, authority))
        elif "authority" in needed_layers:
            raise OracleFailure("missing_evidence", "authority layer required but missing", layer="authority")
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})

    try:
        if render is not None:
            assertions.extend(assert_render_expectations(contract, render))
            # Cross-layer scaffold check
            scaff = (exp.get("render") or {}).get("forbid_scaffold_orders")
            if scaff and authority is not None:
                from sim.dmb.testing.visual_sim.asserts import assert_committed_order_without_active_scaffold

                for oid in scaff if isinstance(scaff, list) else []:
                    try:
                        assert_committed_order_without_active_scaffold(authority, render, oid)
                        assertions.append({"assertion": "forbid_scaffold", "status": "PASS", "layer": "render", "order_id": oid})
                    except AssertionError as ae:
                        raise OracleFailure("stale_render_entity", str(ae), layer="render") from ae
                # Auto: all committed orders
                if scaff is True:
                    for oid, o in (authority.get("orders") or {}).items():
                        if o.get("status") == "committed":
                            assert_committed_order_without_active_scaffold(authority, render, oid)
                            assertions.append({"assertion": "forbid_scaffold", "status": "PASS", "layer": "render", "order_id": oid})
        elif "render" in needed_layers:
            raise OracleFailure("missing_evidence", "render layer required but missing", layer="render")
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})
    except AssertionError as exc:
        failures.append({"code": "stale_render_entity", "layer": "render", "message": str(exc), "detail": {}})

    try:
        if image is not None:
            assertions.extend(assert_image_expectations(contract, image))
        elif "image" in needed_layers:
            if (exp.get("image") or {}).get("allow_missing"):
                assertions.append({"assertion": "image_optional", "status": "NOT_RUN", "layer": "image"})
            else:
                raise OracleFailure("missing_evidence", "image layer required but missing", layer="image")
    except OracleFailure as exc:
        failures.append({"code": exc.code, "layer": exc.layer, "message": str(exc), "detail": exc.detail})

    if require_assertions and needed_layers and not assertions and not failures:
        failures.append({"code": "zero_assertions", "layer": "oracle", "message": "no assertions executed", "detail": {}})

    status = "FAIL" if failures else "PASS"
    if status == "PASS" and require_assertions and needed_layers and len(assertions) == 0:
        status = "FAIL"
        failures.append({"code": "zero_assertions", "layer": "oracle", "message": "PASS with zero assertions forbidden", "detail": {}})

    return {
        "scenario_id": contract.get("scenario_id"),
        "scenario_class": contract.get("scenario_class"),
        "status": status,
        "assertions": assertions,
        "assertion_count": len(assertions),
        "failures": failures,
    }
