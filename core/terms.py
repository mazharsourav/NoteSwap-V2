"""Semesters written the way Bangladeshi students say them: "2-1" is year 2, semester 1.

A note stores `year` (1-5) and `semester` within that year (1-3: some universities run three terms
a year). Older notes may have a semester counted from the start of the degree ("Sem 6"); those don't
fit a "2-1" label, so they show as "Year 1, Sem 6" and only appear under "All semesters"."""

YEARS = range(1, 6)
SEMESTERS = range(1, 4)

# The chips everyone sees; 1-3, 5-1 and so on are added only when some note is for them.
STANDARD = [(year, semester) for year in range(1, 5) for semester in (1, 2)]


def fits(year, semester):
    return year in YEARS and semester in SEMESTERS


def label(year, semester):
    """'2-1' for year 2, semester 1."""
    return f'{year}-{semester}'


def describe(year, semester):
    """How a note's semester is shown: '2-1', or 'Year 1, Sem 6' for an older note that doesn't fit."""
    return label(year, semester) if fits(year, semester) else f'Year {year}, Sem {semester}'


def parse(text):
    """(2, 1) for '2-1'; None for anything else."""
    year, dash, semester = str(text or '').strip().partition('-')
    if dash and year.isdigit() and semester.isdigit() and fits(int(year), int(semester)):
        return int(year), int(semester)
    return None


def choices():
    """For the upload form's Semester dropdown: 1-1, 1-2, 1-3, 2-1 ... 5-3."""
    return [('', 'Choose the semester')] + [
        (label(y, s), f'{label(y, s)}  ·  Year {y}, semester {s}') for y in YEARS for s in SEMESTERS]


def chip_terms(pairs):
    """The chips to show, in order: the standard eight plus any other term in `pairs` (year, semester)."""
    extra = {pair for pair in pairs if fits(*pair)} - set(STANDARD)
    return sorted(set(STANDARD) | extra)
