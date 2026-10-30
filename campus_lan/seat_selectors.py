"""Inclusive campus location ranges; predicates never expand ranges or contact seats."""
from dataclasses import dataclass
import re

NUMBER=r'\d{1,3}(?::\d{1,3})?'
PATTERN=re.compile(r'(?:c|cluster)('+NUMBER+r')(?:r('+NUMBER+r'))?(?:s('+NUMBER+r'))?',re.I)


def bounds(value,maximum):
    parts=list(map(int,value.split(':')))
    low,high=parts[0],parts[-1]
    if not 1<=low<=high<=maximum:
        raise ValueError('Location ranges must ascend and stay within clusters 1–2, rows/seats 1–254.')
    return low,high


def label(value):
    return str(value[0]) if value[0]==value[1] else str(value[0])+':'+str(value[1])


@dataclass(frozen=True)
class SeatSelection:
    clusters:tuple
    rows:tuple|None=None
    seats:tuple|None=None

    def matches(self,location):
        return bool(location and len(location)==3 and all(limit is None or limit[0]<=number<=limit[1]
                    for number,limit in zip(location,(self.clusters,self.rows,self.seats))))

    def __str__(self):
        return 'c'+label(self.clusters)+('r'+label(self.rows) if self.rows else '')+('s'+label(self.seats) if self.seats else '')


def parse_seat_selection(value):
    match=PATTERN.fullmatch(value)
    if not match:raise ValueError('Use c1r3:6, c1r3s1:4 or c1:2r3:4s1:2; : means an inclusive range.')
    cluster,row,seat=match.groups()
    return SeatSelection(bounds(cluster,2),bounds(row,254) if row else None,bounds(seat,254) if seat else None)
