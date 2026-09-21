#include "hexwars.h"

static t_hw_state g_state;
static t_hw_action g_action;
static t_hw_attributes g_attributes;

int hw_state(void)
{
	return ((int)&g_state);
}

int hw_config(void)
{
	g_attributes.growth = 3;
	g_attributes.attack = 3;
	g_attributes.armor = 3;
	bot_config(&g_attributes);
	return ((int)&g_attributes);
}

int hw_step(void)
{
	g_action.from = -1;
	g_action.to = -1;
	g_action.units = 0;
	bot_turn(&g_state, &g_action);
	return ((int)&g_action);
}
