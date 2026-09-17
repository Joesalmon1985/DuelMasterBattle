"""T025 hex board topology checks."""

from __future__ import annotations

from sim.dmb.world.board import HexBoard


def test_radius2_counts() -> None:
    board = HexBoard.radius2()
    assert len(board.hexes) == 19
    assert len(board.nodes) == 54
    assert len(board.edges) == 72


def test_degree_and_touching_limits() -> None:
    board = HexBoard.radius2()
    for node in board.nodes:
        assert 2 <= len(board.adjacent_nodes(node)) <= 3
        assert 1 <= len(board.touching_hexes(node)) <= 3


def test_reciprocal_adjacency_and_edges() -> None:
    board = HexBoard.radius2()
    for node in board.nodes:
        for other in board.adjacent_nodes(node):
            assert node in board.adjacent_nodes(other)
            edge = board.edge(node, other)
            assert edge is not None
            assert board.edge(other, node) == edge
            ends = board.edge_nodes(edge)
            assert set(ends) == {node, other}


def test_shortest_paths_agree_with_distance() -> None:
    board = HexBoard.radius2()
    samples = [
        (board.nodes[0], board.nodes[10]),
        (board.nodes[3], board.nodes[40]),
        (board.nodes[20], board.nodes[20]),
    ]
    for a, b in samples:
        dist = board.distance(a, b)
        path = board.shortest_path(a, b)
        assert len(path) - 1 == dist
        for i in range(len(path) - 1):
            assert path[i + 1] in board.adjacent_nodes(path[i])
