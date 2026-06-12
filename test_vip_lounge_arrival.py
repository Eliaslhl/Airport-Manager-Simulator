#!/usr/bin/env python3
"""Test VIP reaching lounge and transitioning to ATTEND_EMBARQUEMENT."""

from entities import Passenger, PassengerState, LoungeBlock, PlaneState
from game_engine import GameEngine

print("=== Testing VIP Reaching Lounge ===\n")

# Create game engine
map_text = """MMMMMMMMMMMMMMMMMMM
MWMCCMXXMSMSMAMGMVVM
MMMMMMMMMMMMMMMMMMM"""

engine = GameEngine(map_text)
engine.initialize(total_passengers=5, spawn_rate=10.0, plane_depart_time=180.0)

# Create test passengers
vip1 = Passenger((5, 5), is_vip=True)
vip2 = Passenger((5, 5), is_vip=True)

# Add to engine
engine.passengers = [vip1, vip2]

# VIP1: already in VA_PORTE, in the lounge cell but not exactly on the slot
vip1.state = PassengerState.VA_PORTE
vip_lounge = engine.vip_lounge_blocks[0]
vip1.assigned_lounge_block = vip_lounge
vip1.assigned_lounge_slot = 0
vip1.assigned_target_cell = vip_lounge.position
vip1.assigned_target_pos = vip_lounge.get_slot_position(0)

# Put VIP1 in the lounge cell, but slightly offset (would fail with near_target check)
cell_x, cell_y = vip_lounge.position
vip1.x = cell_x + 0.1  # In the cell, but not on the exact slot position
vip1.y = cell_y + 0.1

print(f"VIP1 position: ({vip1.x:.2f}, {vip1.y:.2f})")
print(f"VIP1 target cell: {vip1.assigned_target_cell}")
print(f"VIP1 target pos: {vip1.assigned_target_pos}")
print(f"VIP1 initial state: {vip1.state.name}")

# VIP2: normal case - exactly on the slot
vip2.state = PassengerState.VA_PORTE
vip2.assigned_lounge_block = vip_lounge
vip2.assigned_lounge_slot = 1
vip2.assigned_target_cell = vip_lounge.position
vip2.assigned_target_pos = vip_lounge.get_slot_position(1)
vip2.x, vip2.y = vip2.assigned_target_pos

print(f"\nVIP2 position: ({vip2.x:.2f}, {vip2.y:.2f})")
print(f"VIP2 target pos: {vip2.assigned_target_pos}")
print(f"VIP2 initial state: {vip2.state.name}")

# Update passenger states (simulate _update_passenger_state)
print("\n--- After calling reached_assigned_target() ---")

# Test VIP1 (in cell but not exactly on slot)
if vip1.reached_assigned_target(radius=0.6):
    print(f"\nVIP1 reached target (in cell or exact position)")
    vip1.x, vip1.y = vip1.assigned_target_pos
    vip1.set_state(PassengerState.ATTEND_EMBARQUEMENT)
    print(f"VIP1 new position: ({vip1.x:.2f}, {vip1.y:.2f})")
    print(f"VIP1 new state: {vip1.state.name}")
else:
    print(f"\nVIP1 did NOT reach target")

# Test VIP2 (exactly on slot)
if vip2.reached_assigned_target(radius=0.6):
    print(f"\nVIP2 reached target (in cell or exact position)")
    vip2.x, vip2.y = vip2.assigned_target_pos
    vip2.set_state(PassengerState.ATTEND_EMBARQUEMENT)
    print(f"VIP2 new state: {vip2.state.name}")
else:
    print(f"\nVIP2 did NOT reach target")

# Verify
print("\n=== Results ===")
if vip1.state == PassengerState.ATTEND_EMBARQUEMENT:
    print("✓ VIP1 successfully reached lounge (via cell detection)")
else:
    print("✗ VIP1 failed to reach lounge")

if vip2.state == PassengerState.ATTEND_EMBARQUEMENT:
    print("✓ VIP2 successfully reached lounge (exact position)")
else:
    print("✗ VIP2 failed to reach lounge")

print("\n=== Test Complete ===")
