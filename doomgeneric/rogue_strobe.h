// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_STROBE_H
#define ROGUE_STROBE_H
#include <stdio.h>
#include "p_mobj.h"
#include "d_player.h"
void Rogue_StrobeReset(void);
void Rogue_StrobeLoad(void);
void Rogue_StrobeTick(void);
void Rogue_StrobeShot(player_t *player);
int Rogue_StrobeIlluminated(mobj_t *actor);
void Rogue_StrobeView(int enabled);
void Rogue_StrobeSync(int phase);
void Rogue_StrobeJSON(FILE *out);
#endif
