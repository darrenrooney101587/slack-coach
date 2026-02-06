#!/usr/bin/env python3
"""Autocrop transparent margins and resize PNG to Slack-friendly square size (default 72x72).
Usage: python scripts/prepare_slack_image.py img.png --size 72 --out img_slack.png
"""
import sys
from PIL import Image
from pathlib import Path

def autocrop(image: Image.Image) -> Image.Image:
    # If image has alpha, use it to crop transparent edges; else return as-is
    if image.mode in ('RGBA', 'LA'):
        bg = Image.new('RGBA', image.size, (255,255,255,0))
        bbox = image.getbbox()
        if bbox:
            return image.crop(bbox)
    else:
        bbox = image.getbbox()
        if bbox:
            return image.crop(bbox)
    return image


def main(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('src', help='source image path')
    p.add_argument('--size', type=int, default=72, help='output square size (pixels)')
    p.add_argument('--out', default='img_slack.png', help='output path')
    args = p.parse_args(argv[1:])

    src = Path(args.src)
    out = Path(args.out)
    if not src.exists():
        print('Source not found', file=sys.stderr)
        return 2

    img = Image.open(src).convert('RGBA')
    cropped = autocrop(img)
    # Make square by padding with transparent background
    w,h = cropped.size
    s = max(w,h)
    new = Image.new('RGBA', (s,s), (255,255,255,0))
    new.paste(cropped, ((s-w)//2, (s-h)//2))
    resized = new.resize((args.size, args.size), Image.LANCZOS)
    resized.save(out)
    print(f'Wrote {out} {resized.size[0]}x{resized.size[1]}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
