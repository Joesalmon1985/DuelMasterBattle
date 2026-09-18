from fractions import Fraction
from itertools import permutations

from sim.dmb.industry.allocation import RateAllocator
from sim.dmb.industry.constraints import AllocationRequest, CapacityConstraint
from sim.dmb.industry.routes import FactoryRoute


def _requests():
    return [
        AllocationRequest(f"factory:{i}", FactoryRoute(f"factory:{i}", "processor:1", f"unit.{i}", cost), Fraction(1), Fraction(1, 60))
        for i, cost in enumerate((2, 3, 5), 1)
    ]


def _processor(capacity: Fraction):
    return CapacityConstraint(
        "processor:1",
        capacity,
        {"factory:1": Fraction(2), "factory:2": Fraction(3), "factory:3": Fraction(5)},
        "processor_capacity",
    )


def test_shared_processor_oracles() -> None:
    allocator = RateAllocator()
    assert set(allocator.solve(_requests(), [_processor(Fraction(1, 10))]).rates.values()) == {Fraction(1, 100)}
    assert set(allocator.solve(_requests(), [_processor(Fraction(1, 40))]).rates.values()) == {Fraction(1, 400)}


def test_permutation_invariance_and_stable_result() -> None:
    expected = None
    for ordering in permutations(_requests()):
        rates = RateAllocator().solve(ordering, [_processor(Fraction(1, 10))]).rates
        expected = rates if expected is None else expected
        assert rates == expected


def test_last_finite_hundredth_is_never_duplicated() -> None:
    requests = [
        AllocationRequest(f"f:{i}", FactoryRoute(f"f:{i}", "p", f"u.{i}", 1), Fraction(1), Fraction(1))
        for i in (1, 2)
    ]
    # 0.01 balance / 0.1-second tick = 0.1 units/second aggregate.
    finite = CapacityConstraint("layer:shared", Fraction(1, 10), {"f:1": Fraction(1), "f:2": Fraction(1)}, "finite")
    plan = RateAllocator().solve(requests, [finite])
    assert plan.rates == {"f:1": Fraction(1, 20), "f:2": Fraction(1, 20)}
    assert sum(plan.rates.values()) * Fraction(1, 10) == Fraction(1, 100)


def test_theoretical_mode_is_only_a_plan_marker() -> None:
    constraint = _processor(Fraction(1, 10))
    plan = RateAllocator().solve(_requests(), [constraint], theoretical=True)
    assert plan.theoretical is True
    assert constraint.capacity == Fraction(1, 10)
