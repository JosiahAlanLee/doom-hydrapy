// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_VENDING_H
#define ROGUE_VENDING_H
#include <stdio.h>
#include "d_player.h"
#ifdef DOOM_ROGUE
void Rogue_VendingLoad(void);
void Rogue_VendingTick(void);
int Rogue_VendingUse(player_t *p);
void Rogue_VendingClose(void);
void Rogue_VendingBuy(FILE *out, unsigned id, unsigned slot);
void Rogue_VendingJSON(FILE *out);
int Rogue_HealthCap(player_t *p, int base);
int Rogue_UpgradeDamage(mobj_t *target, mobj_t *source, int damage);
int Rogue_MoveScale(player_t *p, int thrust);
#else
#define Rogue_HealthCap(p, base) (base)
#define Rogue_UpgradeDamage(target, source, damage) (damage)
#define Rogue_MoveScale(p, thrust) (thrust)
#define Rogue_VendingLoad() ((void)0)
#define Rogue_VendingUse(p) 0
#endif
#endif
