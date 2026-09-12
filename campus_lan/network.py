"""Campus seat addressing, based on the campus layout supplied by the owner."""
import re

def seat_address(seat):
    match = re.fullmatch(r'c([12])r(\d{1,3})s(\d{1,3})',seat.strip().lower())
    if not match:
        raise ValueError('Use c1r2s3, with cluster 1 or 2.')
    cluster,row,seat = map(int,match.groups())
    if not 1<=row<=254 or not 1<=seat<=254:
        raise ValueError('Row and seat must be between 1 and 254.')
    return f'10.{10+cluster}.{row}.{seat}'

def address(value):
    if value.lower().startswith('c') and re.match(r'c\d',value.lower()):
        return seat_address(value)
    return value

def ask_seat():
    print('Find your friend at https://meta.intra.42.fr/clusters')
    while True:
        cluster = input('Friend server cluster (1 or 2; blank cancels): ').strip()
        if not cluster:
            return None
        row = input('Row: ').strip()
        seat = input('Seat: ').strip()
        try:
            result = seat_address(f'c{cluster}r{row}s{seat}')
        except ValueError as e:
            print(e)
            continue
        print(f'Connecting to c{cluster}r{row}s{seat} at {result}')
        return result
