"""T032 construction orders quote/reserve/commit/cancel."""

from __future__ import annotations

from sim.dmb.construction.orders import ConstructionService
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.board import HexBoard


def _ready_world() -> tuple[WorldState, HexBoard, ConstructionService]:
    board = HexBoard.radius2()
    state = WorldState(world_id=WorldId("world:t032"), ids=IdAllocator(WorldId("world:t032")))
    state.board["topology"] = board.to_dict()
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    # Seed owned road so settlement at b is reachable
    c = [n for n in board.adjacent_nodes(b) if n != a][0]
    state.roads["seed"] = {"id": "seed", "a": a, "b": b, "faction_id": "f:1"}
    # Existing settlement far away so b is free
    far = board.nodes[20]
    state.settlements["home"] = {
        "id": "home",
        "node_id": a,
        "faction_id": "f:1",
        "tier": "settlement",
        "operational": True,
    }
    store = "store:home"
    ledger = StockLedger(state)
    for good, qty in {"timber": 5, "brick": 5, "wool": 5, "grain": 5, "ore": 5}.items():
        ledger.credit(store, good, qty)
    svc = ConstructionService(state, ledger=ledger, board=board)
    return state, board, svc


def test_remote_unshipped_cannot_pay() -> None:
    state, board, svc = _ready_world()
    ledger = StockLedger(state)
    ledger.credit("store:remote", "timber", 10)
    ledger.credit("store:remote", "brick", 10)
    # Home store empty of wool/grain needed besides what's there — drain wool at home
    state.stocks["store:home"]["catan"]["wool"]["available"] = 0
    q = svc.quote("settlement", faction_id="f:1", store_id="store:home", target_node=board.adjacent_nodes(board.nodes[0])[0])
    assert q["status"] == "blocked"
    assert q["reason"] == "insufficient_local_goods"


def test_commit_debits_once() -> None:
    state, board, svc = _ready_world()
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    # Clear adjacent settlement block: home is on a, settling b is adjacent — blocked!
    # Move home settlement off adjacency: remove home settlement for this test site
    # Use a node adjacent to road but not to another settlement.
    # Put home settlement nowhere adjacent: delete home, only keep road seed from a-b,
    # settle at c beyond b.
    del state.settlements["home"]
    neighbours_b = [n for n in board.adjacent_nodes(b) if n != a]
    c = neighbours_b[0]
    state.roads["seed2"] = {"id": "seed2", "a": b, "b": c, "faction_id": "f:1"}
    order = svc.reserve_order(
        "settlement",
        faction_id="f:1",
        store_id="store:home",
        target_node=c,
    )
    assert order["status"] == "ready"
    before = StockLedger(state).available("store:home", "timber")
    committed = svc.commit_delivered(order["id"])
    assert committed["status"] == "committed"
    after = StockLedger(state).available("store:home", "timber")
    # timber was reserved (not available) then consumed from reserved — available unchanged from post-reserve
    assert after == before
    again = svc.commit_delivered(order["id"])
    assert again["status"] == "committed"
    assert StockLedger(state).available("store:home", "timber") == after
    assert len([s for s in state.settlements.values() if s.get("node_id") == c]) == 1


def test_illegal_target_reclaims() -> None:
    state, board, svc = _ready_world()
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    # Reserve while legal, then place hostile adjacent to invalidate
    del state.settlements["home"]
    neighbours_b = [n for n in board.adjacent_nodes(b) if n != a]
    c = neighbours_b[0]
    state.roads["seed2"] = {"id": "seed2", "a": b, "b": c, "faction_id": "f:1"}
    order = svc.reserve_order("settlement", faction_id="f:1", store_id="store:home", target_node=c)
    assert order["status"] == "ready"
    # Make illegal: put adjacent settlement
    adj = board.adjacent_nodes(c)[0]
    state.settlements["blocker"] = {
        "id": "blocker",
        "node_id": adj,
        "faction_id": "f:2",
        "tier": "settlement",
        "operational": True,
    }
    timber_reserved = StockLedger(state).reserved("store:home", "timber")
    assert timber_reserved == 1
    result = svc.commit_delivered(order["id"])
    assert result["status"] == "blocked"
    assert result.get("reclaimed") is True
    assert StockLedger(state).available("store:home", "timber") >= 4


def test_ten_vp_interrupt() -> None:
    state, board, svc = _ready_world()
    del state.settlements["home"]
    # Give faction 10 VP via five cities
    for i in range(5):
        state.settlements[f"c{i}"] = {
            "id": f"c{i}",
            "node_id": f"node:x{i}",
            "faction_id": "f:1",
            "tier": "city",
            "operational": True,
        }
    assert ScoreService(state).score("f:1") == 10
    # Commit a road to trigger threshold check
    a = board.nodes[0]
    b = board.adjacent_nodes(a)[0]
    nxt = [n for n in board.adjacent_nodes(b) if n != a][0]
    order = svc.reserve_order(
        "road",
        faction_id="f:1",
        store_id="store:home",
        target_edge=(b, nxt),
    )
    result = svc.commit_delivered(order["id"])
    assert result.get("interrupt", {}).get("kind") == "vp_threshold"
    assert "f:1" in result["interrupt"]["factions"]
