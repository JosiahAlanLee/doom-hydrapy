// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_CREATURE_H
#define ROGUE_CREATURE_H
#include <stdio.h>
#include "p_mobj.h"
#ifdef DOOM_ROGUE
void Rogue_CreatureReset(void);
int Rogue_CreatureThink(mobj_t *actor);
void Rogue_CreatureVisual(mobj_t *actor);
void Rogue_CreatureHurt(mobj_t *actor);
void Rogue_CreatureRemove(mobj_t *actor);
void Rogue_PlayerFilter(struct player_s *player);
void Rogue_CreatureJSON(FILE *out,mobj_t *actor);
void Rogue_CreatureStatus(FILE *out);
#else
#define Rogue_CreatureReset() ((void)0)
#define Rogue_CreatureThink(actor) 0
#define Rogue_CreatureHurt(actor) ((void)0)
#define Rogue_CreatureRemove(actor) ((void)0)
#define Rogue_PlayerFilter(player) ((void)0)
#endif
#endif
