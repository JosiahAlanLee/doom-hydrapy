// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef ROGUE_ARCH_H
#define ROGUE_ARCH_H
#include <stdio.h>
#include "p_mobj.h"
#ifdef DOOM_ROGUE
void Rogue_ArchReset(void);
void Rogue_ArchLoad(void);
void Rogue_ArchTick(void);
void Rogue_ArchJSON(FILE *out);
boolean P_RogueRelocate(mobj_t *thing,fixed_t x,fixed_t y,fixed_t offset_z);
#else
#define Rogue_ArchReset() ((void)0)
#define Rogue_ArchLoad() ((void)0)
#define Rogue_ArchTick() ((void)0)
#endif
#endif
