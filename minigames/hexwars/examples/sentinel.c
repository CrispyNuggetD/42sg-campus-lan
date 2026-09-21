#include "hexwars.h"

void bot_config(t_hw_attributes *attributes)
{
	attributes->growth = 2;
	attributes->attack = 2;
	attributes->armor = 5;
}

/* A deliberately simple beginner bot: wait, then overwhelm a weak neighbor. */
void bot_turn(const t_hw_state *state, t_hw_action *action)
{
	int i;
	int d;
	int n;

	i = -1;
	while (++i < state->cell_count)
	{
		if (state->cells[i].owner != state->me)
			continue ;
		d = -1;
		while (++d < 6)
		{
			n = state->cells[i].neighbors[d];
			if (n >= 0 && state->cells[n].owner != state->me
				&& state->cells[i].units > 2 * state->cells[n].units + 5)
			{
				action->from = i;
				action->to = n;
				action->units = state->cells[i].units - 3;
				return ;
			}
		}
	}
}
