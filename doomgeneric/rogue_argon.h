// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_ARGON_H
#define ROGUE_ARGON_H
#include <stdio.h>
#include "p_mobj.h"
#ifdef DOOM_ROGUE
int Rogue_ArgonThink(mobj_t *actor);
void Rogue_ArgonVisual(mobj_t *actor);
void Rogue_ArgonHurt(mobj_t *actor);
void Rogue_ArgonJSON(FILE *out,mobj_t *actor);
void Rogue_ArgonStatus(FILE *out);
#else
#define Rogue_ArgonThink(actor) 0
#define Rogue_ArgonVisual(actor) ((void)0)
#define Rogue_ArgonHurt(actor) ((void)0)
#endif
#endif
