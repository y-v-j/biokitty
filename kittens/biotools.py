#!/usr/bin/env python3
"""biokitty sequence tools — the engine behind the ctrl+shift+b bindings.

Reads a sequence on stdin (raw, or one or more FASTA records) and writes the
result to stdout. Deliberately dependency-free and terminal-agnostic: kitty
pipes a selection into it, but it works just as well in a pipeline.

    printf 'ATGGCCTAA' | biotools.py revcomp
    biotools.py stats < reads.fasta
    kitten @ get-text | biotools.py translate --frame 2

Commands
    revcomp     reverse complement (IUPAC aware, case preserved)
    complement  complement without reversing
    translate   DNA/RNA -> protein, standard genetic code
    stats       length, GC%, composition, per-record for FASTA
    clean       strip headers, digits and whitespace -> bare sequence
    wrap        rewrap sequence to a fixed line width
    orf         longest open reading frame in any of the 6 frames
    selftest    verify the tables against known cases
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterator

# --- tables ----------------------------------------------------------------

# Full IUPAC nucleotide ambiguity set, both cases. Gap characters map to
# themselves so aligned sequences survive a round trip.
_COMPLEMENT = str.maketrans(
    'ACGTURYSWKMBDHVNacgturyswkmbdhvn-.',
    'TGCAAYRSWMKVHDBNtgcaayrswmkvhdbn-.',
)

# Standard genetic code (NCBI translation table 1).
CODON_TABLE = {
    'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
    'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
    'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
    'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
    'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
    'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
    'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
    'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
    'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
    'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
    'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
    'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
    'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
    'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
    'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
    'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
}

STOP = '*'


# --- parsing ---------------------------------------------------------------

class Record:
    __slots__ = ('header', 'seq')

    def __init__(self, header: str, seq: str) -> None:
        self.header = header
        self.seq = seq

    @property
    def name(self) -> str:
        return self.header.split()[0] if self.header else '(unnamed)'


def parse(text: str) -> list[Record]:
    """Parse FASTA, or treat the whole input as one unnamed sequence.

    Anything that is not a residue character is dropped from sequence lines,
    which is what makes pasted, numbered alignment output usable directly.
    """
    if '>' not in text:
        seq = ''.join(c for c in text if not c.isspace() and not c.isdigit())
        return [Record('', seq)] if seq else []

    records: list[Record] = []
    header: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith('>'):
            if header is not None:
                records.append(Record(header, ''.join(chunks)))
            header = line[1:].strip()
            chunks = []
        elif header is not None:
            chunks.append(''.join(c for c in line if not c.isspace() and not c.isdigit()))
    if header is not None:
        records.append(Record(header, ''.join(chunks)))
    return records


# --- operations ------------------------------------------------------------

def complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)


def revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def translate(seq: str, frame: int = 1, to_stop: bool = False) -> str:
    """Translate in frame 1..3 (forward) or -1..-3 (reverse complement)."""
    if frame < 0:
        seq = revcomp(seq)
        offset = -frame - 1
    else:
        offset = frame - 1
    seq = seq.upper().replace('U', 'T')

    out: list[str] = []
    for i in range(offset, len(seq) - 2, 3):
        aa = CODON_TABLE.get(seq[i:i + 3], 'X')
        if aa == STOP and to_stop:
            break
        out.append(aa)
    return ''.join(out)


def gc_percent(seq: str) -> float:
    s = seq.upper()
    acgt = sum(s.count(b) for b in 'ACGT')
    if not acgt:
        return 0.0
    return 100.0 * (s.count('G') + s.count('C')) / acgt


def longest_orf(seq: str) -> tuple[str, int, int]:
    """Longest ATG..stop peptide across all six frames.

    Returns (peptide, frame, nucleotide_start). Start is 0-based on the
    original forward sequence for positive frames, on the reverse complement
    for negative ones.
    """
    best = ('', 0, 0)
    for frame in (1, 2, 3, -1, -2, -3):
        prot = translate(seq, frame)
        i = 0
        while True:
            start = prot.find('M', i)
            if start < 0:
                break
            end = prot.find(STOP, start)
            peptide = prot[start:end] if end >= 0 else prot[start:]
            if len(peptide) > len(best[0]):
                nt = (abs(frame) - 1) + start * 3
                best = (peptide, frame, nt)
            i = start + 1
    return best


# --- output ----------------------------------------------------------------

def wrap(seq: str, width: int = 60) -> Iterator[str]:
    for i in range(0, len(seq), width):
        yield seq[i:i + width]


def emit(records: list[Record], transform, width: int, out) -> None:
    for rec in records:
        result = transform(rec.seq)
        if rec.header:
            print(f'>{rec.header}', file=out)
        if width > 0:
            for line in wrap(result, width):
                print(line, file=out)
        else:
            print(result, file=out)


def describe(rec: Record, out) -> None:
    seq = rec.seq
    s = seq.upper()
    n = len(seq)
    print(f'{rec.name}', file=out)
    print(f'  length      {n}', file=out)
    if not n:
        return

    counts = {b: s.count(b) for b in 'ACGTUN'}
    nucleotide = sum(counts.values())
    is_nt = nucleotide >= 0.85 * n

    if is_nt:
        print(f'  GC          {gc_percent(seq):.1f}%', file=out)
        for b in 'ACGTUN':
            if counts[b]:
                print(f'  {b}           {counts[b]:>8}  {100.0 * counts[b] / n:5.1f}%', file=out)
        ambiguous = n - nucleotide
        if ambiguous:
            print(f'  ambiguous   {ambiguous:>8}', file=out)
        # ~660 g/mol per bp for double-stranded DNA
        print(f'  dsDNA mass  {n * 660 / 1000:.1f} kDa', file=out)
    else:
        print('  type        protein (or mostly non-nucleotide)', file=out)
        residues = sorted({c for c in s if c.isalpha()})
        print(f'  residues    {"".join(residues)}', file=out)


# --- self test -------------------------------------------------------------

def selftest() -> int:
    failures = []

    def check(label, got, want):
        if got != want:
            failures.append(f'{label}: got {got!r}, want {want!r}')

    check('revcomp', revcomp('ATGC'), 'GCAT')
    check('revcomp iupac', revcomp('ACGTRYKM'), 'KMRYACGT')
    check('revcomp case', revcomp('atgc'), 'gcat')
    check('revcomp gap', revcomp('AT-GC'), 'GC-AT')
    check('complement', complement('ATGC'), 'TACG')
    # Start codon, alanine, stop.
    check('translate f1', translate('ATGGCCTAA'), 'MA*')
    check('translate to_stop', translate('ATGGCCTAA', to_stop=True), 'MA')
    check('translate rna', translate('AUGGCCUAA'), 'MA*')
    check('translate frame2', translate('GATGGCCTAA', frame=2), 'MA*')
    # Reverse strand of ATGGCCTAA is TTAGGCCAT; frame -1 reads TTA GGC CAT.
    check('translate frame-1', translate('ATGGCCTAA', frame=-1), 'LGH')
    check('gc', round(gc_percent('GGCC'), 1), 100.0)
    check('gc mixed', round(gc_percent('ATGC'), 1), 50.0)
    check('gc empty', gc_percent(''), 0.0)
    check('parse raw', parse('ATGC')[0].seq, 'ATGC')
    check('parse strips digits', parse('1 ATGC 60')[0].seq, 'ATGC')
    check('parse fasta n', len(parse('>a\nATGC\n>b\nGGGG\n')), 2)
    check('parse fasta seq', parse('>a\nAT\nGC\n')[0].seq, 'ATGC')
    check('parse fasta name', parse('>seq1 desc here\nATGC\n')[0].name, 'seq1')
    check('orf', longest_orf('AAATGGCCGGCTAAAA')[0], 'MAG')
    check('unknown codon', translate('ATGNNNTAA'), 'MX*')

    for f in failures:
        print('FAIL ' + f, file=sys.stderr)
    print(f'{"FAILED" if failures else "ok"}: {len(failures)} failure(s)',
          file=sys.stderr if failures else sys.stdout)
    return 1 if failures else 0


# --- cli -------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog='biotools.py',
        description='Sequence utilities for biokitty. Reads stdin, writes stdout.')
    p.add_argument('command',
                   choices=['revcomp', 'complement', 'translate', 'stats',
                            'clean', 'wrap', 'orf', 'selftest'])
    p.add_argument('--frame', type=int, default=1,
                   help='translation frame: 1..3 forward, -1..-3 reverse (default 1)')
    p.add_argument('--to-stop', action='store_true',
                   help='stop translating at the first stop codon')
    p.add_argument('--width', type=int, default=60,
                   help='output line width; 0 for a single line (default 60)')
    args = p.parse_args(argv)

    if args.command == 'selftest':
        return selftest()

    if args.frame not in (1, 2, 3, -1, -2, -3):
        print('--frame must be one of 1 2 3 -1 -2 -3', file=sys.stderr)
        return 2

    text = sys.stdin.read()
    records = parse(text)
    if not records:
        print('no sequence found on stdin', file=sys.stderr)
        return 1

    out = sys.stdout
    if args.command == 'revcomp':
        emit(records, revcomp, args.width, out)
    elif args.command == 'complement':
        emit(records, complement, args.width, out)
    elif args.command == 'translate':
        emit(records, lambda s: translate(s, args.frame, args.to_stop), args.width, out)
    elif args.command == 'clean':
        emit(records, lambda s: s, 0, out)
    elif args.command == 'wrap':
        emit(records, lambda s: s, args.width or 60, out)
    elif args.command == 'stats':
        for i, rec in enumerate(records):
            if i:
                print(file=out)
            describe(rec, out)
    elif args.command == 'orf':
        for rec in records:
            peptide, frame, start = longest_orf(rec.seq)
            print(f'{rec.name}  frame {frame:+d}  start {start}  len {len(peptide)}', file=out)
            for line in wrap(peptide, args.width or 60):
                print(line, file=out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
