import re

PARA = re.compile(r"^(\d+)\.(?:\s|$)")
NUM_POINT = re.compile(r"^(\d+)\)(?:\s|$)")
LET_POINT = re.compile(r"^([a-z])\)(?:\s|$)")


def structure(text):
    """Paragraph and point labels in order, read from line starts, e.g. ['1', '3(a)', '(16)(b)']."""
    labels, top = [], None
    for line in text.split("\n"):
        line = line.strip()
        if m := PARA.match(line):
            top = m.group(1); labels.append(top)
        elif m := NUM_POINT.match(line):
            top = f"({m.group(1)})"; labels.append(top)
        elif m := LET_POINT.match(line):
            labels.append(f"{top}({m.group(1)})" if top else f"({m.group(1)})")
    return labels


def gaps(labels):
    """Numbering problems: tops not 1..n, letters not a..z in order under each top."""
    problems, tops, letters = [], [], {}
    for lab in labels:
        m = re.fullmatch(r"\(?(\d+)\)?(?:\(([a-z])\))?", lab)
        n, letter = int(m.group(1)), m.group(2)
        if letter is None:
            tops.append(n)
        else:
            letters.setdefault(n, []).append(letter)
    if tops != list(range(1, len(tops) + 1)):
        problems.append(f"top-level numbering {tops}")
    for n, ls in letters.items():
        if ls != [chr(ord("a") + i) for i in range(len(ls))]:
            problems.append(f"letters under {n}: {ls}")
    return problems
