// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_AI_H
#define ROGUE_AI_H
#include <stdio.h>
#include "p_mobj.h"
#ifdef DOOM_ROGUE
int Rogue_Class(mobj_t *actor);
void Rogue_Apply(mobj_t *actor, mapthing_t *thing);
int Rogue_Damage(mobj_t *actor, int damage);
int Rogue_Fan(mobj_t *actor);
void Rogue_Projectile(mobj_t *source, mobj_t *missile);
void Rogue_Visual(mobj_t *actor);
void Rogue_Report(FILE *out);
#else
#define Rogue_Class(actor) 0
#define Rogue_Apply(actor, thing) ((void)0)
#define Rogue_Damage(actor, damage) (damage)
#define Rogue_Fan(actor) 0
#define Rogue_Projectile(source, missile) ((void)0)
#define Rogue_Visual(actor) ((void)0)
#endif
#endif
