import math

class OptimizationService:
    @staticmethod
    def distance(p1, p2):
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    @staticmethod
    def optimize_cutting_path(segments):
        """
        Optimizes the order of cutting segments to minimize air travel distance.
        Uses Greedy Nearest Neighbor algorithm.
        
        Args:
            segments: List of tuples representing lines [(x1, y1, x2, y2), ...]
            
        Returns:
            dict: {
                'optimized_path': List of segments in new order (potentially flipped),
                'original_distance': float,
                'optimized_distance': float,
                'saved_percent': float
            }
        """
        if not segments:
            return {
                'optimized_path': [],
                'original_distance': 0,
                'optimized_distance': 0,
                'saved_percent': 0
            }

        # 1. Calculate Original Air Travel (Sequential as given)
        original_air_travel = 0
        current_pos = (0, 0)
        for seg in segments:
            start = (seg[0], seg[1])
            end = (seg[2], seg[3])
            # Travel to start
            original_air_travel += OptimizationService.distance(current_pos, start)
            # Cut (processing time, ignored for air travel comparison, but technically distance is same)
            # We focusing on AIR TRAVEL (move without cutting)
            current_pos = end
            
        # 2. Optimize
        remaining = segments[:]
        optimized_path = []
        current_pos = (0, 0)
        optimized_air_travel = 0
        
        while remaining:
            best_dist = float('inf')
            best_idx = -1
            best_orientation = 0 # 0: normal (start->end), 1: flipped (end->start)
            
            for i, seg in enumerate(remaining):
                p1 = (seg[0], seg[1])
                p2 = (seg[2], seg[3])
                
                # Check distance to P1
                dist1 = OptimizationService.distance(current_pos, p1)
                if dist1 < best_dist:
                    best_dist = dist1
                    best_idx = i
                    best_orientation = 0
                    
                # Check distance to P2 (if we cut backwards)
                dist2 = OptimizationService.distance(current_pos, p2)
                if dist2 < best_dist:
                    best_dist = dist2
                    best_idx = i
                    best_orientation = 1
            
            # Select best next segment
            seg = remaining.pop(best_idx)
            
            if best_orientation == 0:
                # Cut from P1 to P2
                optimized_path.append(seg)
                optimized_air_travel += best_dist
                current_pos = (seg[2], seg[3])
            else:
                # Cut from P2 to P1 (Flip segment representation for output)
                # Output: (x2, y2, x1, y1)
                optimized_path.append((seg[2], seg[3], seg[0], seg[1]))
                optimized_air_travel += best_dist
                current_pos = (seg[0], seg[1])
                
        # Calculate savings
        if original_air_travel > 0:
            saved_percent = ((original_air_travel - optimized_air_travel) / original_air_travel) * 100
        else:
            saved_percent = 0
            
        return {
            'optimized_path': optimized_path,
            'original_distance': round(original_air_travel, 2),
            'optimized_distance': round(optimized_air_travel, 2),
            'saved_percent': round(saved_percent, 2)
        }
