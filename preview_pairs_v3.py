"""Read-only review of dedupe CSV; supports moved images and conflict groups."""
import argparse
import csv
from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageOps, ImageDraw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--report', type=Path, default=Path('dedupe_report.csv'))
    p.add_argument('--mode', choices=['duplicate','conflict'], default='duplicate')
    p.add_argument('--min', type=int, default=0)
    p.add_argument('--max', type=int, default=256)
    p.add_argument('--n', type=int, default=12)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--out', type=Path, default=Path('pairs_v2.jpg'))
    a = p.parse_args()
    if not a.root.is_dir() or a.n < 1 or a.offset < 0:
        p.error('Invalid root, n or offset')
    root = a.root.resolve()
    moved = root.with_name(root.name + '_duplicates')
    groups = defaultdict(list)
    with a.report.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['group']:
                groups[r['group']].append(r)
    pairs = []
    ref_action = 'keep' if a.mode == 'duplicate' else 'conflict-keep'
    for gid, rows in groups.items():
        ref = next((r for r in rows if r['action'] == ref_action), None)
        if ref is None:
            continue
        for r in rows:
            if r['action'] == a.mode and a.min <= int(r['dist_to_kept']) <= a.max:
                pairs.append((int(r['dist_to_kept']), gid, ref, r))
    pairs.sort(key=lambda x: (-x[0], int(x[1]), x[3]['path']))
    total = len(pairs)
    pairs = pairs[a.offset:a.offset+a.n]
    if not pairs:
        raise SystemExit('No matching pairs in this range.')
    tile, cw, ch = 260, 560, 365
    sheet = Image.new('RGB', (cw*2, ch*((len(pairs)+1)//2)), 'white')
    draw = ImageDraw.Draw(sheet)
    errors = []
    def place(row, x, y):
        rel = Path(row['path'].replace('\\','/'))
        candidates = [root/rel, moved/rel, root.with_name(root.name + '_conflicts')/rel]
        allowed_roots = (root, moved.resolve(), root.with_name(root.name + '_conflicts').resolve())
        found = [q for q, parent in zip(candidates, allowed_roots)
                 if not rel.is_absolute() and '..' not in rel.parts
                 and q.resolve().is_relative_to(parent) and q.is_file()]
        status = ['DATASET', 'DUPLICATES', 'CONFLICTS'][candidates.index(found[0])] if found else 'MISSING'
        try:
            if len(found) != 1:
                raise ValueError('missing or ambiguous path')
            with Image.open(found[0]) as im:
                im = ImageOps.exif_transpose(im).convert('RGB')
                im.thumbnail((tile,tile))
                draw.rectangle((x,y,x+tile,y+tile),fill='#eeeeee')
                sheet.paste(im,(x+(tile-im.width)//2,y+(tile-im.height)//2))
        except Exception as e:
            status = 'MISSING / ERROR'
            errors.append((row['path'],str(e)))
            draw.rectangle((x,y,x+tile,y+tile),fill='#fddddd')
            draw.text((x+10,y+100),status,fill='black')
        draw.text((x,y+tile+4),f"{row['split']} | {status}",fill='black')
        label = row['class']
        for j in range(0,len(label),32):
            draw.text((x,y+tile+18+12*(j//32)),label[j:j+32],fill='black')
    for i,(d,g,k,r) in enumerate(pairs):
        x,y=(i%2)*cw+10,(i//2)*ch+8
        draw.text((x,y),f'#{a.offset+i+1} | Group {g} | Hamming {d} | {a.mode}',fill='black')
        place(k,x,y+20)
        place(r,x+270,y+20)
    with a.out.open('xb') as stream:
        sheet.save(stream, format='JPEG', quality=92)
    print(f'Saved {a.out.resolve()} | pairs {a.offset+1}-{a.offset+len(pairs)} / {total}')
    for path,error in errors:
        print(f'ERROR {path}: {error}')
    print(f'Image read errors: {len(errors)}. No dataset files modified.')

if __name__ == '__main__':
    main()
