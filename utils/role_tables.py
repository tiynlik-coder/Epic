"""Role line-ups by player count for the Baku role sets (classic / super / mega / real).

Each table is (base roles, [(min_players, role), ...]). A game with n players gets the base roles plus
every role whose threshold is <= n; the rest are Tinch axoli (mega: Bo‘ri/Tulki).
"WOLF" is Bo‘ri or Tulki depending on the chat setting. Keys: "<roleset>" or "<mode>:<roleset>".
"""

ROLE_TABLES = {
    "classic": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Mafia'), (9, 'Serjant'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Daydi'), (13, 'Rais'), (14, 'Qotil'), (15, 'WOLF'), (16, 'Janob'),
        (17, 'Mafia'), (18, 'Konchi'), (19, 'Jurnalist'), (20, 'Fotoparatchi'), (21, 'Aferist'),
        (22, 'Sotqin'), (23, 'G‘azabkor'), (24, 'Yollanma qotil'), (25, 'Suidsid'), (26, 'Ayg‘oqchi'),
        (27, 'Serjant'), (28, 'Mafia'), (29, 'Sehrgar'), (31, 'Qaroqchi'), (32, 'Joker'), (33, 'Mafia'),
        (34, 'Robin Gud'), (35, 'Minior'), (36, 'WOLF'), (37, 'Kimyogar'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Admiral'),
    ]),
    "super": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Omadli'), (9, 'Robin Gud'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Joker'), (13, 'Janob'), (14, 'G‘azabkor'), (15, 'Ayg‘oqchi'), (16, 'Minior'),
        (17, 'Yollanma qotil'), (18, 'Konchi'), (19, 'Sehrgar'), (20, 'Fotoparatchi'), (21, 'Kimyogar'),
        (22, 'Qaroqchi'), (23, 'Qotil'), (24, 'Daydi'), (25, 'Jurnalist'), (26, 'WOLF'), (27, 'Sotqin'),
        (28, 'Mafia'), (29, 'Admiral'), (30, 'WOLF'), (31, 'Serjant'), (32, 'Afsungar'), (33, 'Mafia'),
        (34, 'Serjant'), (35, 'Rais'), (36, 'WOLF'), (37, 'Aferist'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Suidsid'),
    ]),
    "mega": (['Don', 'Komissar Katani', 'Shifokor', 'Daydi'], [
        (5, 'Kezuvchi'), (6, 'Mafia'), (7, 'Kimyogar'), (8, 'Ayg‘oqchi'), (9, 'Serjant'), (10, 'Labarant'),
        (11, 'Rais'), (12, 'Hamshira'), (13, 'Qaroqchi'), (14, 'Minior'), (15, 'Yollanma qotil'),
        (16, 'Konchi'), (17, 'Admiral'), (18, 'WOLF'), (19, 'Robin Gud'), (20, 'Joker'), (21, 'Qotil'),
        (22, 'Mafia'), (23, 'WOLF'), (24, 'Janob'), (25, 'Sotqin'), (26, 'Mafia'), (27, 'Sehrgar'),
        (28, 'Afsungar'), (29, 'Serjant'), (30, 'Afsungar'), (31, 'Mafia'), (32, 'Serjant'),
        (33, 'Fotoparatchi'), (34, 'Jurnalist'), (35, 'Aferist'), (36, 'Mafia'), (37, 'Afsungar'),
        (38, 'Suidsid'), (39, 'Mafia'), (40, 'Omadli'),
    ]),
    "real": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Omadli'), (9, 'Robin Gud'), (10, 'Qotil'),
        (11, 'Advokat'), (12, 'Koldun'), (13, 'Janob'), (14, 'Minior'), (15, 'Ayg‘oqchi'), (16, 'Labarant'),
        (17, 'Serjant'), (18, 'WOLF'), (19, 'Sehrgar'), (20, 'Fotoparatchi'), (21, 'Joker'), (22, 'Qaroqchi'),
        (23, 'Yollanma qotil'), (24, 'Daydi'), (25, 'Jurnalist'), (26, 'Kimyogar'), (27, 'Sotqin'),
        (28, 'Mafia'), (29, 'Admiral'), (30, 'WOLF'), (32, 'Afsungar'), (33, 'Mafia'), (34, 'Serjant'),
        (36, 'WOLF'), (37, 'Aferist'), (38, 'Mafia'), (39, 'Afsungar'),
    ]),
    "vs:classic": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Mafia'), (9, 'Serjant'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Daydi'), (13, 'WOLF'), (14, 'Qotil'), (15, 'Ayg‘oqchi'), (16, 'WOLF'),
        (17, 'Mafia'), (18, 'WOLF'), (19, 'Jurnalist'), (20, 'Fotoparatchi'), (21, 'Aferist'), (22, 'Sotqin'),
        (23, 'G‘azabkor'), (24, 'Mafia'), (25, 'Suidsid'), (26, 'WOLF'), (27, 'Serjant'), (28, 'Mafia'),
        (29, 'Sehrgar'), (31, 'WOLF'), (32, 'Joker'), (33, 'Mafia'), (34, 'Robin Gud'), (35, 'Minior'),
        (36, 'WOLF'), (37, 'Kimyogar'), (38, 'Mafia'), (39, 'Afsungar'), (40, 'Serjant'),
    ]),
    "vs:super": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Omadli'), (9, 'Robin Gud'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Joker'), (13, 'WOLF'), (14, 'G‘azabkor'), (15, 'Ayg‘oqchi'), (16, 'Minior'),
        (17, 'Mafia'), (18, 'WOLF'), (19, 'Sehrgar'), (20, 'Fotoparatchi'), (21, 'Kimyogar'), (22, 'WOLF'),
        (23, 'Qotil'), (24, 'Daydi'), (25, 'Jurnalist'), (26, 'WOLF'), (27, 'Sotqin'), (28, 'Mafia'),
        (29, 'Serjant'), (30, 'WOLF'), (31, 'Serjant'), (32, 'Afsungar'), (33, 'Mafia'), (34, 'Serjant'),
        (35, 'Rais'), (36, 'WOLF'), (37, 'Aferist'), (38, 'Mafia'), (39, 'Afsungar'), (40, 'Suidsid'),
    ]),
    "vs:mega": (['Don', 'Komissar Katani', 'Shifokor', 'Daydi'], [
        (5, 'Kezuvchi'), (6, 'Mafia'), (7, 'Robin Gud'), (8, 'Qotil'), (9, 'Labarant'), (10, 'Joker'),
        (11, 'WOLF'), (12, 'Hamshira'), (13, 'WOLF'), (14, 'Minior'), (15, 'Mafia'), (16, 'WOLF'),
        (17, 'Sehrgar'), (18, 'Fotoparatchi'), (19, 'Kimyogar'), (20, 'Serjant'), (21, 'Qotil'),
        (22, 'Mafia'), (23, 'Jurnalist'), (24, 'Qaroqchi'), (25, 'Sotqin'), (26, 'Mafia'), (27, 'Serjant'),
        (28, 'WOLF'), (29, 'Serjant'), (30, 'Afsungar'), (31, 'Mafia'), (32, 'Serjant'), (33, 'Ayg‘oqchi'),
        (34, 'WOLF'), (35, 'Aferist'), (36, 'Mafia'), (37, 'Afsungar'), (38, 'Suidsid'), (39, 'Mafia'),
        (40, 'Omadli'),
    ]),
    "zombie:classic": (['Don', 'Komissar Katani', 'Zombi'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Mafia'), (9, 'Serjant'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Daydi'), (13, 'Rais'), (14, 'Qotil'), (15, 'Ayg‘oqchi'), (16, 'Janob'),
        (17, 'Mafia'), (18, 'Konchi'), (19, 'Jurnalist'), (20, 'Fotoparatchi'), (21, 'Aferist'),
        (22, 'Sotqin'), (23, 'G‘azabkor'), (24, 'Yollanma qotil'), (25, 'Suidsid'), (26, 'WOLF'),
        (27, 'Serjant'), (28, 'Mafia'), (29, 'Sehrgar'), (31, 'Qaroqchi'), (32, 'Joker'), (33, 'Mafia'),
        (34, 'Robin Gud'), (35, 'Minior'), (36, 'WOLF'), (37, 'Kimyogar'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Admiral'),
    ]),
    "zombie:super": (['Don', 'Komissar Katani', 'Zombi'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Omadli'), (9, 'Robin Gud'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Joker'), (13, 'Janob'), (14, 'G‘azabkor'), (15, 'Ayg‘oqchi'), (16, 'Minior'),
        (17, 'Yollanma qotil'), (18, 'Konchi'), (19, 'Sehrgar'), (20, 'Fotoparatchi'), (21, 'Kimyogar'),
        (22, 'Qaroqchi'), (23, 'Qotil'), (24, 'Daydi'), (25, 'Jurnalist'), (26, 'WOLF'), (27, 'Sotqin'),
        (28, 'Mafia'), (29, 'Admiral'), (30, 'WOLF'), (31, 'Serjant'), (32, 'Afsungar'), (33, 'Mafia'),
        (34, 'Serjant'), (35, 'Rais'), (36, 'WOLF'), (37, 'Aferist'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Suidsid'),
    ]),
    "zombie:mega": (['Don', 'Komissar Katani', 'Shifokor', 'Zombi'], [
        (5, 'Daydi'), (6, 'Kezuvchi'), (7, 'Mafia'), (8, 'Robin Gud'), (9, 'G‘azabkor'), (10, 'Labarant'),
        (11, 'Joker'), (12, 'Rais'), (13, 'Hamshira'), (14, 'Janob'), (15, 'Minior'), (16, 'Yollanma qotil'),
        (17, 'Konchi'), (18, 'Sehrgar'), (19, 'Fotoparatchi'), (20, 'Kimyogar'), (21, 'Serjant'),
        (22, 'Qotil'), (23, 'Mafia'), (24, 'Jurnalist'), (25, 'Qaroqchi'), (26, 'Sotqin'), (27, 'Mafia'),
        (28, 'Admiral'), (29, 'WOLF'), (30, 'Serjant'), (31, 'Afsungar'), (32, 'Mafia'), (33, 'Serjant'),
        (34, 'Ayg‘oqchi'), (35, 'WOLF'), (36, 'Aferist'), (37, 'Mafia'), (38, 'Afsungar'), (39, 'Suidsid'),
        (40, 'Omadli'),
    ]),
    "para:classic": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Mafia'), (9, 'Serjant'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Daydi'), (13, 'Rais'), (14, 'Qotil'), (15, 'Ayg‘oqchi'), (16, 'WOLF'),
        (17, 'Mafia'), (18, 'Konchi'), (19, 'Jurnalist'), (20, 'Fotoparatchi'), (21, 'Aferist'),
        (22, 'Sotqin'), (23, 'G‘azabkor'), (24, 'Yollanma qotil'), (25, 'Suidsid'), (26, 'WOLF'),
        (27, 'Serjant'), (28, 'Mafia'), (29, 'Sehrgar'), (31, 'Qaroqchi'), (32, 'Joker'), (33, 'Mafia'),
        (34, 'Robin Gud'), (35, 'Minior'), (36, 'WOLF'), (37, 'Kimyogar'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Admiral'),
    ]),
    "para:super": (['Don', 'Komissar Katani'], [
        (5, 'Shifokor'), (6, 'Mafia'), (7, 'Kezuvchi'), (8, 'Omadli'), (9, 'Robin Gud'), (10, 'Afsungar'),
        (11, 'Advokat'), (12, 'Joker'), (13, 'WOLF'), (14, 'G‘azabkor'), (15, 'Ayg‘oqchi'), (16, 'Minior'),
        (17, 'Mafia'), (18, 'Konchi'), (19, 'Sehrgar'), (20, 'Fotoparatchi'), (21, 'Kimyogar'),
        (22, 'Qaroqchi'), (23, 'Qotil'), (24, 'Daydi'), (25, 'Jurnalist'), (26, 'WOLF'), (27, 'Sotqin'),
        (28, 'Mafia'), (29, 'Admiral'), (30, 'WOLF'), (31, 'Serjant'), (32, 'Afsungar'), (33, 'Mafia'),
        (34, 'Serjant'), (35, 'Rais'), (36, 'WOLF'), (37, 'Aferist'), (38, 'Mafia'), (39, 'Afsungar'),
        (40, 'Suidsid'),
    ]),
    "para:mega": (['Don', 'Komissar Katani', 'Shifokor', 'Daydi'], [
        (5, 'Kezuvchi'), (6, 'Mafia'), (7, 'Robin Gud'), (8, 'G‘azabkor'), (9, 'Labarant'), (10, 'Joker'),
        (11, 'WOLF'), (12, 'Hamshira'), (13, 'WOLF'), (14, 'Minior'), (15, 'Mafia'), (16, 'WOLF'),
        (17, 'Sehrgar'), (18, 'Fotoparatchi'), (19, 'Kimyogar'), (20, 'Serjant'), (21, 'Qotil'),
        (22, 'Mafia'), (23, 'Jurnalist'), (24, 'Qaroqchi'), (25, 'Sotqin'), (26, 'Mafia'), (27, 'Admiral'),
        (28, 'WOLF'), (29, 'Serjant'), (30, 'Afsungar'), (31, 'Mafia'), (32, 'Serjant'), (33, 'Ayg‘oqchi'),
        (34, 'WOLF'), (35, 'Aferist'), (36, 'Mafia'), (37, 'Afsungar'), (38, 'Suidsid'), (39, 'Mafia'),
        (40, 'Omadli'),
    ]),
}

ROLESETS = ("classic", "super", "mega", "real")


def table_roles(key, n, wolf="Bo‘ri"):
    """Role list (not shuffled) for n players, or None when there is no such table."""
    table = ROLE_TABLES.get(key)
    if not table: return None
    base, steps = table
    roles = list(base) + [r for need, r in steps if n >= need]
    filler = "WOLF" if key.endswith("mega") else "Tinch axoli"
    roles += [filler] * max(0, n - len(roles))
    return [wolf if r == "WOLF" else r for r in roles[:n]]
