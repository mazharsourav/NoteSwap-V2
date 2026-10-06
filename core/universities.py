"""Universities students pick from (UniversityField), and how a stored university is shown.

A listed university is stored as its short code ("UAP"); anything typed under "Other" is stored as
typed (tidied). So `university` fields hold either a code from this list or a free-text name.
Add a university: one line in PUBLIC or PRIVATE (code, full name). Codes must stay unique and never
change once used, because they're what the database stores.
"""
import re

PUBLIC = [
    ('DU', 'University of Dhaka'),
    ('BUET', 'Bangladesh University of Engineering and Technology'),
    ('RU', 'University of Rajshahi'),
    ('CU', 'University of Chittagong'),
    ('JU', 'Jahangirnagar University'),
    ('JnU', 'Jagannath University'),
    ('SUST', 'Shahjalal University of Science and Technology'),
    ('KU', 'Khulna University'),
    ('KUET', 'Khulna University of Engineering & Technology'),
    ('RUET', 'Rajshahi University of Engineering & Technology'),
    ('CUET', 'Chittagong University of Engineering & Technology'),
    ('DUET', 'Dhaka University of Engineering & Technology'),
    ('IUT', 'Islamic University of Technology'),
    ('MIST', 'Military Institute of Science and Technology'),
    ('BUP', 'Bangladesh University of Professionals'),
    ('BUTEX', 'Bangladesh University of Textiles'),
    ('BAU', 'Bangladesh Agricultural University'),
    ('SAU', 'Sher-e-Bangla Agricultural University'),
    ('IU', 'Islamic University, Kushtia'),
    ('CoU', 'Comilla University'),
    ('MBSTU', 'Mawlana Bhashani Science and Technology University'),
    ('NSTU', 'Noakhali Science and Technology University'),
    ('JUST', 'Jashore University of Science and Technology'),
    ('PSTU', 'Patuakhali Science and Technology University'),
    ('HSTU', 'Hajee Mohammad Danesh Science and Technology University'),
    ('BRUR', 'Begum Rokeya University, Rangpur'),
    ('BU', 'University of Barishal'),
    ('NU', 'National University'),
    ('BOU', 'Bangladesh Open University'),
]

PRIVATE = [
    ('NSU', 'North South University'),
    ('BRACU', 'BRAC University'),
    ('IUB', 'Independent University, Bangladesh'),
    ('AIUB', 'American International University-Bangladesh'),
    ('EWU', 'East West University'),
    ('UIU', 'United International University'),
    ('AUST', 'Ahsanullah University of Science and Technology'),
    ('UAP', 'University of Asia Pacific'),
    ('DIU', 'Daffodil International University'),
    ('ULAB', 'University of Liberal Arts Bangladesh'),
    ('IUBAT', 'International University of Business Agriculture and Technology'),
    ('BUBT', 'Bangladesh University of Business and Technology'),
    ('SEU', 'Southeast University'),
    ('SUB', 'State University of Bangladesh'),
    ('GUB', 'Green University of Bangladesh'),
    ('UU', 'Uttara University'),
    ('UODA', 'University of Development Alternative'),
    ('UITS', 'University of Information Technology and Sciences'),
    ('SUBD', 'Stamford University Bangladesh'),
    ('EU', 'Eastern University'),
    ('NUB', 'Northern University Bangladesh'),
    ('PrimeU', 'Prime University'),
    ('WUB', 'World University of Bangladesh'),
    ('BUFT', 'BGMEA University of Fashion & Technology'),
    ('MIU', 'Manarat International University'),
    ('CityU', 'City University'),
    ('IIUC', 'International Islamic University Chittagong'),
    ('USTC', 'University of Science and Technology Chittagong'),
    ('PUC', 'Premier University, Chittagong'),
    ('EDU', 'East Delta University'),
    ('MUS', 'Metropolitan University, Sylhet'),
    ('LUS', 'Leading University, Sylhet'),
]

OTHER = '__other__'  # the picker's "Other (not in the list)" choice

NAMES = dict(PUBLIC + PRIVATE)  # code -> full name

# Other ways people write a listed university (compared after _key()), e.g. old free-text data
ALIASES = {
    'dhaka university': 'DU', 'brac': 'BRACU', 'brac university': 'BRACU', 'bracu': 'BRACU',
    'iub': 'IUB', 'iubat university': 'IUBAT', 'jagannath': 'JnU', 'jnu': 'JnU',
    'national university bangladesh': 'NU', 'stamford': 'SUBD', 'stamford university': 'SUBD',
    'iut': 'IUT', 'buet': 'BUET', 'aust': 'AUST', 'uap': 'UAP', 'asia pacific': 'UAP',
}


def _key(text):
    """Lower case, letters and digits only: 'University of Asia-Pacific ' -> 'universityofasiapacific'."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


_LOOKUP = {}
for _code, _name in PUBLIC + PRIVATE:
    _LOOKUP[_key(_code)] = _code
    _LOOKUP[_key(_name)] = _code
    _LOOKUP[_key(f'{_name} ({_code})')] = _code
for _alias, _code in ALIASES.items():
    _LOOKUP[_key(_alias)] = _code


def normalize(text):
    """The code for a listed university written any common way, otherwise the text tidied up
    (extra spaces removed). Empty stays empty."""
    text = ' '.join((text or '').split())
    return _LOOKUP.get(_key(text), text) if text else ''


def short_name(value):
    """'UAP' for a listed university, the stored name for any other."""
    return value or ''


def full_name(value):
    """'University of Asia Pacific' for a listed university, the stored name for any other."""
    return NAMES.get(value, value or '')


def label(code):
    """How the picker shows a listed university: 'University of Asia Pacific (UAP)'."""
    return f'{NAMES[code]} ({code})'


def choices():
    """Grouped choices for the picker's <select>."""
    return [
        ('', 'Choose your university'),
        ('Public universities', [(code, label(code)) for code, _ in sorted(PUBLIC, key=lambda u: u[1])]),
        ('Private universities', [(code, label(code)) for code, _ in sorted(PRIVATE, key=lambda u: u[1])]),
        (OTHER, 'Other (not in the list)'),
    ]
