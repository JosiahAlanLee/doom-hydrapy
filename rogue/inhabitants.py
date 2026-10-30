# SPDX-License-Identifier: GPL-2.0-or-later
"""Gloamwood interpretations; new Doom art/logic, not imported Bedrock assets.

The recovered add-on READMEs describe the Hollow's watched/tree/crawl rule and
Stone ReDead's telegraphed shriek, bounded grip and hold-to-escape behavior.
Their geometry, textures and sound files are unavailable. These adaptations
keep those encounter identities while using original billboard art.
"""
CREATURES = {
    'hollow': {'name': 'THE HOLLOW', 'class': 7, 'flag': 7, 'type': 66,
               'family': 'SKEL', 'rule': 'It freezes when watched. Look away and it crawls.'},
    'redead': {'name': 'STONE REDEAD', 'class': 8, 'flag': 7, 'type': 65,
               'family': 'CPOS', 'rule': 'Break sight during its shriek. If gripped, hold F or hurt it to escape.'},
}


def options(kind, roll=0):
    """Class 7 is extended by an otherwise unused native actor type.

    Keeping the existing three class bits and four roll bits preserves older
    PWADs and leaves every THING option within a signed 16-bit word.
    """
    from rogue.bosses import BOSSES
    entry = (CREATURES | BOSSES)[kind]
    if not isinstance(roll, int) or isinstance(roll, bool) or not 0 <= roll < 16:
        raise ValueError('roll must be 0..15')
    return 7 | (entry.get('flag', entry['class']) << 8) | (roll << 11)
