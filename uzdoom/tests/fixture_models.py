# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep test-only actor subclasses visible: MODELDEF binds exact class names."""
import re


def bind_fixture_models(files, fixture):
    definitions=files.get('MODELDEF',b'').decode()
    additions=[]
    for child,parent in re.findall(r'\bclass\s+(\w+)\s*:\s*(NRMesh\w+)\b',fixture.decode()):
        # Our generated model blocks contain only flat MODELDEF properties.
        pattern=r'\bModel\s+'+re.escape(parent)+r'\s*\{[^}]*\}'
        match=re.search(pattern,definitions)
        if match is None:raise ValueError('Missing production model for '+parent)
        additions.append(re.sub(r'\b'+re.escape(parent)+r'\b',child,match.group(),count=1))
    files['MODELDEF']=(definitions+'\n'+'\n'.join(additions)+'\n').encode()
