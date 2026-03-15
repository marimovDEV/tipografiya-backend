import os
import sys

# Set up path to import service directly without full Django setup if depends only on math
# But usually good practice to setup Django if we move files around
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.optimization_service import OptimizationService

def verify_optimization():
    print("--- Verifying AI Cutting Path Optimization ---")
    
    # Test Case: 2 parallel lines far from origin, but close to each other
    # Origin (0,0)
    # Line 1: (100, 100) -> (200, 100)
    # Line 2: (100, 110) -> (200, 110)
    # Bad Order: Line 1 then Line 2 (Normal) -> finish at (200,100), travel to (100,110) ~100 units back
    # Optimized: Line 1 then Line 2 (Flipped) -> finish at (200,100), travel to (200,110) ~10 units, cut back to (100,110)
    
    # Let's create a "Zig Zag" scenario that is bad sequentially
    # Segment A: (10, 10) -> (20, 10)
    # Segment B: (10, 20) -> (20, 20)
    # Segment C: (10, 30) -> (20, 30)
    
    # Sequential:
    # 0,0 -> 10,10 (dist ~14) -> cut to 20,10. Pos: 20,10.
    # 20,10 -> 10,20 (dist ~14) -> cut to 20,20. Pos: 20,20.
    # 20,20 -> 10,30 (dist ~14) -> cut to 20,30. Pos: 20,30.
    # Total Air: 14 + 14 + 14 = 42
    
    # Optimization (Nearest Neighbor):
    # 0,0 -> 10,10 (dist ~14) -> cut to 20,10. Pos: 20,10.
    # Nearest to 20,10 is (20,20) [End of B] -> dist 10. 
    # Cut B Reversed: (20,20) -> (10,20). Pos: 10,20.
    # Nearest to 10,20 is (10,30) [Start of C] -> dist 10.
    # Cut C Normal: (10,30) -> (20,30).
    # Total Air: 14 + 10 + 10 = 34.
    # Savings: (42-34)/42 ~ 19%
    
    segments = [
        (10, 10, 20, 10),
        (10, 20, 20, 20),
        (10, 30, 20, 30)
    ]
    
    result = OptimizationService.optimize_cutting_path(segments)
    
    print(f"Original Segments: {len(segments)}")
    print(f"Original Air Distance: {result['original_distance']}")
    print(f"Optimized Air Distance: {result['optimized_distance']}")
    print(f"Savings: {result['saved_percent']}%")
    print("Optimization Path:")
    for seg in result['optimized_path']:
        print(seg)
        
    if result['saved_percent'] > 0:
        print("SUCCESS: Optimization reduced travel distance.")
    else:
        print("FAILURE: No optimization achieved (might be already optimal or bug).")

if __name__ == '__main__':
    verify_optimization()
