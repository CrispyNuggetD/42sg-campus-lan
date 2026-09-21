#include "hexwars.h"

void bot_config(t_hw_attributes *attributes)
{
	attributes->growth = 4;
	attributes->attack = 3;
	attributes->armor = 2;
}

/* Prefer weak enemy tiles; move reserves toward the nearest enemy otherwise. */
static int absolute(int n)
{
	if (n < 0)
		return (-n);
	return (n);
}

static int distance(const t_hw_cell *a, const t_hw_cell *b)
{
	return ((absolute(a->q - b->q) + absolute(a->r - b->r)
			+ absolute(a->q + a->r - b->q - b->r)) / 2);
}

void bot_turn(const t_hw_state *state, t_hw_action *action)
{
	int i;
	int d;
	int n;
	int target;
	int closest;
	int score;
	int best;
	int j;

	best = -100000;
	i = -1;
	while (++i < state->cell_count)
	{
		if (state->cells[i].owner != state->me || state->cells[i].units < 3)
			continue ;
		target = -1;
		closest = 1000;
		j = -1;
		while (++j < state->cell_count)
			if (state->cells[j].owner != state->me
				&& distance(&state->cells[i], &state->cells[j]) < closest)
			{
				target = j;
				closest = distance(&state->cells[i], &state->cells[j]);
			}
		d = -1;
		while (++d < 6 && target >= 0)
		{
			n = state->cells[i].neighbors[d];
			if (n < 0)
				continue ;
			if (state->cells[n].owner != state->me)
				score = 100 + state->cells[i].units - 2 * state->cells[n].units;
			else if (distance(&state->cells[n], &state->cells[target]) < closest
				&& state->cells[n].units + state->cells[i].units < HW_MAX_UNITS)
				score = state->cells[i].units - closest;
			else
				continue ;
			if (score > best)
			{
				best = score;
				action->from = i;
				action->to = n;
				action->units = state->cells[i].units - 1;
			}
		}
	}
}
