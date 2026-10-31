// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_BOSS_H
#define ROGUE_BOSS_H
#include <stdio.h>
#include "p_mobj.h"
#ifdef DOOM_ROGUE
void Rogue_BossReset(void);
void Rogue_BossLoad(void);
void Rogue_BossRegister(mobj_t *actor);
void Rogue_BossTick(void);
int Rogue_BossGuard(mobj_t *target,mobj_t *source);
int Rogue_BossAttack(mobj_t *actor);
int Rogue_ExitAllowed(void);
void Rogue_BossJSON(FILE *out);
void Rogue_BossesJSON(FILE *out);
#else
#define Rogue_BossReset() ((void)0)
#define Rogue_BossLoad() ((void)0)
#define Rogue_BossRegister(actor) ((void)0)
#define Rogue_BossGuard(target, source) 0
#define Rogue_BossAttack(actor) 0
#define Rogue_ExitAllowed() 1
#endif
#endif
