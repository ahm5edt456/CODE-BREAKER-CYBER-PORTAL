"""Spread ordered challenge gates across the maze without blocking the first one."""
from collections import deque
import random

DIRECTIONS=((0,-1,1),(1,0,2),(0,1,4),(-1,0,8))
def edge_key(a,b):return tuple(sorted((a,b)))
def distances(grid,start,blocked=()):
    height=len(grid);width=len(grid[0]);blocked=set(blocked)
    result={start:0};parents={start:None};queue=deque([start])
    while queue:
        x,y=queue.popleft()
        for dx,dy,wall in DIRECTIONS:
            n=(x+dx,y+dy)
            if not(0<=n[0]<width and 0<=n[1]<height) or grid[y][x]&wall:continue
            if edge_key((x,y),n) in blocked or n in result:continue
            result[n]=result[(x,y)]+1;parents[n]=(x,y);queue.append(n)
    return result,parents

def spread_gates(grid,rng=None):
    rng=rng or random
    root_distance,parents=distances(grid,(0,0))
    # Every candidate is well outside the starting corner.
    cells=[p for p in parents if p!=(0,0) and sum(p)>=9 and root_distance[p]>=12]
    paths={}
    for cell in cells:
        cursor=cell;path=set()
        while parents[cursor] is not None:
            path.add(edge_key(cursor,parents[cursor]));cursor=parents[cursor]
        paths[cell]=path
    pairings=[]
    for i,a in enumerate(cells):
        from_a,_=distances(grid,parents[a])
        for b in cells[i+1:]:
            spatial=abs(a[0]-b[0])+abs(a[1]-b[1])
            qa=(a[0]>=6,a[1]>=4);qb=(b[0]>=6,b[1]>=4)
            if spatial<10 or qa==qb:continue
            a_edge=edge_key(a,parents[a]);b_edge=edge_key(b,parents[b])
            first,second=(a,b) if root_distance[a]<=root_distance[b] else (b,a)
            second_edge=edge_key(second,parents[second])
            if second_edge in paths[first]:continue
            travel=from_a[parents[b]]
            if travel<14:continue
            separate_branches=a_edge not in paths[b] and b_edge not in paths[a]
            diagonal=qa[0]!=qb[0] and qa[1]!=qb[1]
            score=spatial*3+min(travel,45)*.4+(15 if separate_branches else 0)+(8 if diagonal else 0)-root_distance[first]*.12-max(0,travel-65)*.3
            pairings.append((score,first,second))
    if not pairings:raise ValueError('Maze has no sufficiently spread challenge locations.')
    best=max(p[0] for p in pairings)
    _,first,second=rng.choice([p for p in pairings if p[0]>=best-5])
    return [edge_key(parents[p],p) for p in (first,second)]
